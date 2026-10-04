"""Contract and state tests with a real local HTTP boundary and mocked provider."""

import copy
import io
import json
import os
import tempfile
import threading
import time
import unittest
from decimal import Decimal
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from mendcart import app, paypal
from mendcart.config import load_env, public_origin
from mendcart.planner import PlanRequest, create_plan_sync
from mendcart.store import DemoStore


class CheckoutHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server.public_origin = cls.origin
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.store_patch = patch.object(app, "STORE", DemoStore())
        self.store_patch.start()
        self.addCleanup(self.store_patch.stop)
        self.env_patch = patch.dict(os.environ, {"PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": "", "PAYPAL_BASE_URL": paypal.SANDBOX_API,
                                                "OPENAI_API_KEY": "", "OPENAI_MODEL": "", "OPENAI_BASE_URL": ""})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.browser = build_opener(HTTPCookieProcessor(CookieJar()))

    def api(self, path, body=None, browser=None, headers=None):
        request = Request(self.origin + path, data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type": "application/json", **(headers or {})}, method="GET" if body is None else "POST")
        try:
            with (browser or self.browser).open(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def plan(self):
        code, result = self.api("/api/plan", {"request": "The water pump leaks, repair the seal", "max_budget": 120})
        self.assertEqual(code, 200, result)
        self.assertTrue(result["policy_passed"])
        self.assertFalse(result["approval_recorded"])
        return result

    def provider_order(self, plan, state="CREATED", value="24.00"):
        order = {"id": "DEMOORDER1", "intent": "CAPTURE", "status": state,
                 "purchase_units": [{"reference_id": plan["plan_id"], "custom_id": plan["plan_id"],
                                     "amount": {"currency_code": "USD", "value": value}}],
                 "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=DEMOORDER1"}]}
        if state == "COMPLETED":
            order["purchase_units"][0]["payments"] = {"captures": [{"id": "DEMOCAPTURE1", "status": "COMPLETED", "amount": {"currency_code": "USD", "value": value}}]}
        return order

    def bind(self, plan):
        provider = self.provider_order(plan)
        with patch.object(app, "sandbox_ready", return_value=True), patch.object(app, "create_order", return_value=provider):
            code, result = self.api("/api/paypal/orders", {"plan_id": plan["plan_id"], "human_approved": True})
        self.assertEqual(code, 200, result)
        return result

    def test_client_total_and_policy_cannot_replace_server_plan(self):
        plan = self.plan()
        code, preview = self.api("/api/paypal/orders", {"plan_id": plan["plan_id"], "human_approved": True,
                                                        "plan": {"subtotal": 0.01, "budget_cap": 999999, "items": []}})
        self.assertEqual(code, 200)
        self.assertEqual(preview["amount"], "24.00")
        self.assertEqual(preview["mode"], "sandbox_preview")
        self.assertIsNone(preview["order_id"])
        self.assertEqual(preview["order"]["purchase_units"][0]["amount"]["breakdown"]["item_total"]["value"], "24.00")

    def test_read_only_preview_never_approves_or_calls_provider(self):
        plan = self.plan()
        record = app.STORE.plans[plan["plan_id"]]
        before = copy.deepcopy(record.events)
        with patch.object(app, "create_order") as create, patch.object(app, "sandbox_ready", return_value=True):
            code, preview = self.api(f"/api/plans/{plan['plan_id']}/preview")
        self.assertEqual(code, 200)
        self.assertEqual(preview["status"], "read_only_preview")
        self.assertFalse(preview["approval_recorded"])
        self.assertEqual(preview["amount"], "24.00")
        self.assertIsNone(record.approved_at)
        self.assertEqual(record.events, before)
        create.assert_not_called()

    def test_plan_and_order_are_owned_by_browser_session(self):
        plan = self.plan()
        self.bind(plan)
        other = build_opener(HTTPCookieProcessor(CookieJar()))
        self.assertEqual(self.api("/api/paypal/orders", {"plan_id": plan["plan_id"], "human_approved": True}, browser=other)[0], 403)
        self.assertEqual(self.api("/api/paypal/capture", {"order_id": "DEMOORDER1"}, browser=other)[0], 403)
        self.assertEqual(self.api("/api/paypal/orders/DEMOORDER1", browser=other)[0], 403)

    def test_expired_or_unapproved_plans_are_blocked(self):
        plan = self.plan()
        self.assertEqual(self.api("/api/paypal/orders", {"plan_id": plan["plan_id"]})[0], 403)
        app.STORE.plans[plan["plan_id"]].expires = time.time() - 1
        self.assertEqual(self.api("/api/paypal/orders", {"plan_id": plan["plan_id"], "human_approved": True})[0], 422)

    def test_policy_blocked_plan_cannot_be_approved(self):
        code, plan = self.api("/api/plan", {"request": "Need repair tools", "max_budget": 5})
        self.assertEqual(code, 200)
        self.assertFalse(plan["policy_passed"])
        self.assertEqual(self.api("/api/plans/approve", {"plan_id": plan["plan_id"], "human_approved": True})[0], 422)

    def test_payer_boolean_cannot_bypass_provider_approval(self):
        plan = self.plan()
        self.bind(plan)
        with patch.object(app, "get_order", return_value=self.provider_order(plan, "CREATED")), patch.object(app, "capture_order") as capture:
            code, _ = self.api("/api/paypal/capture", {"order_id": "DEMOORDER1", "payer_approved": True})
        self.assertEqual(code, 403)
        capture.assert_not_called()

    def test_provider_amount_mismatch_blocks_capture(self):
        plan = self.plan()
        self.bind(plan)
        with patch.object(app, "get_order", return_value=self.provider_order(plan, "APPROVED", "99.00")), patch.object(app, "capture_order") as capture:
            code, _ = self.api("/api/paypal/capture", {"order_id": "DEMOORDER1"})
        self.assertEqual(code, 502)
        capture.assert_not_called()

    def test_approved_capture_is_idempotent_and_sanitized(self):
        plan = self.plan()
        self.bind(plan)
        completed = self.provider_order(plan, "COMPLETED")
        completed["payer"] = {"email_address": "private-sandbox-payer@example.test"}
        with patch.object(app, "get_order", return_value=self.provider_order(plan, "APPROVED")), patch.object(app, "capture_order", return_value=completed) as capture:
            code, first = self.api("/api/paypal/capture", {"order_id": "DEMOORDER1"})
            second_code, second = self.api("/api/paypal/capture", {"order_id": "DEMOORDER1"})
        self.assertEqual((code, second_code), (200, 200))
        self.assertEqual(first["status"], "COMPLETED")
        self.assertEqual(first["captures"], second["captures"])
        capture.assert_called_once()
        self.assertNotIn("private-sandbox", json.dumps(first))

    def test_completed_provider_order_recovers_lost_capture_response(self):
        plan = self.plan()
        self.bind(plan)
        with patch.object(app, "get_order", return_value=self.provider_order(plan, "COMPLETED")), patch.object(app, "capture_order") as capture:
            code, result = self.api("/api/paypal/capture", {"order_id": "DEMOORDER1"})
        self.assertEqual(code, 200)
        self.assertEqual(result["status"], "COMPLETED")
        capture.assert_not_called()

    def test_capture_response_may_omit_full_order_fields(self):
        plan = self.plan()
        self.bind(plan)
        capture_response = self.provider_order(plan, "COMPLETED")
        del capture_response["intent"]
        del capture_response["purchase_units"][0]["custom_id"]
        del capture_response["purchase_units"][0]["amount"]
        with patch.object(app, "get_order", return_value=self.provider_order(plan, "APPROVED")), patch.object(app, "capture_order", return_value=capture_response):
            code, result = self.api("/api/paypal/capture", {"order_id": "DEMOORDER1"})
        self.assertEqual(code, 200)
        self.assertEqual(result["captures"][0]["id"], "DEMOCAPTURE1")

    def test_capture_amount_mismatch_is_not_accepted(self):
        plan = self.plan()
        self.bind(plan)
        with patch.object(app, "get_order", return_value=self.provider_order(plan, "APPROVED")), patch.object(app, "capture_order", return_value=self.provider_order(plan, "COMPLETED", "25.00")):
            code, result = self.api("/api/paypal/capture", {"order_id": "DEMOORDER1"})
        self.assertEqual(code, 502)
        self.assertIn("capture amount", result["detail"])
        self.assertIsNone(app.STORE.plans[plan["plan_id"]].capture)

    def test_order_retries_reuse_same_request_id_and_payload(self):
        plan = self.plan()
        with patch.object(app, "sandbox_ready", return_value=True), patch.object(app, "create_order", side_effect=[paypal.PayPalError("Retry sandbox request."), self.provider_order(plan)]) as create:
            self.assertEqual(self.api("/api/paypal/orders", {"plan_id": plan["plan_id"], "human_approved": True})[0], 502)
            self.assertEqual(self.api("/api/paypal/orders", {"plan_id": plan["plan_id"], "human_approved": True})[0], 200)
            self.assertEqual(self.api("/api/paypal/orders", {"plan_id": plan["plan_id"]})[0], 200)
        self.assertEqual(create.call_count, 2)
        self.assertEqual(create.call_args_list[0], create.call_args_list[1])

    def test_return_order_details_restore_plan(self):
        plan = self.plan()
        self.bind(plan)
        with patch.object(app, "get_order", return_value=self.provider_order(plan, "APPROVED")):
            code, result = self.api("/api/paypal/orders/DEMOORDER1")
        self.assertEqual(code, 200)
        self.assertEqual(result["plan"]["plan_id"], plan["plan_id"])
        self.assertTrue(result["plan"]["approval_recorded"])

    def test_cross_origin_or_non_object_requests_are_blocked(self):
        self.assertEqual(self.api("/api/plan", {"request": "repair tools", "max_budget": 50}, headers={"Origin": "https://other.example"})[0], 403)
        self.assertEqual(self.api("/api/plan", ["not a request object"])[0], 422)


class PayPalContractTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"PAYPAL_BASE_URL": paypal.SANDBOX_API, "PAYPAL_CLIENT_ID": "sandbox-client", "PAYPAL_CLIENT_SECRET": "sandbox-secret", "OPENAI_API_KEY": "", "OPENAI_BASE_URL": "", "OPENAI_MODEL": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        paypal._token_cache.clear()

    def test_exact_sandbox_origin_only(self):
        for endpoint in ["https://api-m.paypal.com", "https://sandbox.example", "https://api-m.sandbox.paypal.com.evil.test", "http://api-m.sandbox.paypal.com", "https://user@api-m.sandbox.paypal.com", "https://api-m.sandbox.paypal.com:444", "https://api-m.sandbox.paypal.com/extra"]:
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {"PAYPAL_BASE_URL": endpoint}):
                with self.assertRaises(ValueError):
                    paypal._base_url()
        self.assertEqual(paypal._base_url(), paypal.SANDBOX_API)

    def test_orders_v2_breakdown_and_return_urls(self):
        plan = create_plan_sync(PlanRequest(request="Repair leaking water pump seal", max_budget=100))
        payload = paypal.order_payload(plan, "server-plan", "http://127.0.0.1:8000")
        amount = payload["purchase_units"][0]["amount"]
        self.assertEqual(amount["value"], "24.00")
        self.assertEqual(amount["breakdown"]["item_total"], {"currency_code": "USD", "value": "24.00"})
        context = payload["payment_source"]["paypal"]["experience_context"]
        self.assertTrue(context["return_url"].endswith("/?paypal=return"))
        self.assertTrue(context["cancel_url"].endswith("/?paypal=cancel"))
        self.assertEqual(payload["purchase_units"][0]["custom_id"], "server-plan")

    def test_oauth_headers_and_request_id(self):
        class Response(io.BytesIO):
            pass
        with patch.object(paypal, "_open", side_effect=[Response(b'{"access_token":"fixture-token","expires_in":300}'), Response(b'{"id":"ORDER1"}'), Response(b'{"id":"ORDER1","status":"APPROVED"}')]) as transport:
            paypal._call("POST", "/v2/checkout/orders", {"intent": "CAPTURE"}, "idempotency-uuid")
            paypal.get_order("ORDER1")
        oauth = transport.call_args_list[0].args[0]
        post = transport.call_args_list[1].args[0]
        details = transport.call_args_list[2].args[0]
        self.assertEqual(oauth.data, b"grant_type=client_credentials")
        self.assertTrue(oauth.get_header("Authorization").startswith("Basic "))
        self.assertEqual(post.get_header("Paypal-request-id"), "idempotency-uuid")
        self.assertEqual(post.get_header("Authorization"), "Bearer fixture-token")
        self.assertEqual(details.get_method(), "GET")
        self.assertEqual(transport.call_count, 3)

    def test_provider_errors_hide_response_and_secrets(self):
        failure = HTTPError(paypal.SANDBOX_API, 401, "sandbox-secret", {}, io.BytesIO(b'{"secret":"sandbox-secret"}'))
        with patch.object(paypal, "_open", side_effect=failure):
            with self.assertRaises(paypal.PayPalError) as caught:
                paypal._access_token()
        self.assertNotIn("sandbox-secret", str(caught.exception))
        self.assertIn("HTTP 401", str(caught.exception))

    def test_approval_links_cannot_leave_sandbox(self):
        with self.assertRaises(paypal.PayPalError):
            paypal.approval_url({"links": [{"rel": "payer-action", "href": "https://www.paypal.com/checkoutnow"}]})

    def test_dotenv_load_does_not_execute_or_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / ".env"
            file.write_text("MENDCART_ENV_FIXTURE='literal $(ignored)'\nMENDCART_ENV_EXISTING=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"MENDCART_ENV_EXISTING": "from-environment"}):
                os.environ.pop("MENDCART_ENV_FIXTURE", None)
                load_env(file)
                self.assertEqual(os.environ["MENDCART_ENV_FIXTURE"], "literal $(ignored)")
                self.assertEqual(os.environ["MENDCART_ENV_EXISTING"], "from-environment")

    def test_public_origin_requires_https_outside_localhost(self):
        for origin in ["http://example.test", "https://user@example.test", "https://example.test/path", "https://example.test?token=x"]:
            with self.subTest(origin=origin), patch.dict(os.environ, {"MENDCART_PUBLIC_URL": origin}):
                with self.assertRaises(ValueError):
                    public_origin()

    def test_money_rejects_nonfinite_fractional_and_negative(self):
        for value in ["NaN", "Infinity", "1.001", "-1"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                paypal.money(value)
        self.assertEqual(paypal.money("24.00"), Decimal("24.00"))


if __name__ == "__main__":
    unittest.main()
