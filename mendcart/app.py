"""Standard-library local demo with server-owned approval and sandbox orders."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from decimal import Decimal
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, urlsplit

from .catalog import CATALOG_AS_OF, public_catalog
from .config import load_env, public_origin
from .paypal import PayPalError, approval_url, capture_order, create_order, get_order, money, order_payload, sandbox_ready
from .planner import PlanRequest, create_plan_sync
from .store import DemoStore, PlanRecord, timestamp

ROOT = Path(__file__).resolve().parent.parent
load_env(ROOT / ".env")
STORE = DemoStore()
COOKIE = "mendcart_session"


def status() -> dict:
    error = None
    try:
        ready = sandbox_ready()
    except ValueError as exc:
        ready, error = False, str(exc)
    return {
        "paypal_mode": "sandbox" if ready else "sandbox demo preview",
        "sandbox_credentials_configured": ready,
        "paypal_configuration_error": error,
        "ai_mode": "external structured model" if all(os.getenv(k) for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")) else "local supervised TF-IDF intent model",
        "planner_engine": "external-structured-model" if all(os.getenv(k) for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")) else "local-tfidf-knn-v1",
        "catalog_as_of": CATALOG_AS_OF,
        "catalog_is_synthetic": True,
        "live_integrations": False,
        "payment_state": "in-memory session-owned sandbox demo",
    }


def _checkout_plan(record: PlanRecord) -> dict:
    """Revalidate canonical rows and original limits from server memory."""
    plan, request = record.plan, record.request
    if not plan.get("policy_passed") or not plan.get("approval_required"):
        raise ValueError("Plan did not pass checkout policy checks.")
    if request.get("currency") != "USD":
        raise ValueError("Sandbox checkout supports USD only.")
    approved = {item["sku"]: item for item in public_catalog()}
    total, rows, seen = Decimal("0"), [], set()
    for row in plan.get("items", []):
        sku, quantity = row.get("sku"), row.get("quantity")
        item = approved.get(sku)
        if (not item or sku in seen or not item["approved"] or item["supplier_id"] not in request["allowed_suppliers"]
                or type(quantity) is not int or not 1 <= quantity <= min(5, item["stock"])):
            raise ValueError("Server plan contains an ineligible SKU, supplier, or quantity. Generate a new plan.")
        seen.add(sku)
        line = money(item["unit_price"]) * quantity
        total += line
        rows.append({**item, "quantity": quantity, "line_total": float(line)})
    cap = money(request["max_budget"])
    if not rows or not 0 < total <= min(cap, Decimal("300")) or total != money(plan["subtotal"]):
        raise ValueError("Current catalog total does not match the approved plan or exceeds its budget. Generate a new plan.")
    return {**plan, "items": rows, "subtotal": float(total), "currency": "USD", "budget_cap": float(cap)}


def _verify_order(record: PlanRecord, order: dict) -> None:
    if order.get("id") != record.order["id"] or order.get("intent") != "CAPTURE":
        raise PayPalError("PayPal order does not match the stored sandbox checkout.")
    units = order.get("purchase_units", [])
    if len(units) != 1:
        raise PayPalError("PayPal order contains an unexpected purchase unit.")
    unit = units[0]
    amount = unit.get("amount", {})
    if (unit.get("reference_id") != record.plan_id or unit.get("custom_id") != record.plan_id
            or amount.get("currency_code") != "USD" or money(amount.get("value")) != money(record.plan["subtotal"])):
        raise PayPalError("PayPal amount or plan reference does not match server approval.")


def _verify_capture(record: PlanRecord, captured: dict) -> None:
    # Capture responses omit order-level amount/custom_id/intent in PayPal's API
    # examples. The pre-capture GET already verifies those immutable fields.
    if captured.get("id") != record.order["id"]:
        raise PayPalError("Sandbox capture belongs to an unexpected order.")
    units = captured.get("purchase_units", [])
    if len(units) != 1 or units[0].get("reference_id") != record.plan_id:
        raise PayPalError("Sandbox capture does not match the stored plan reference.")
    captures = units[0].get("payments", {}).get("captures", [])
    seen, total = set(), Decimal("0")
    for capture in captures:
        capture_id, amount = capture.get("id"), capture.get("amount", {})
        if not isinstance(capture_id, str) or not capture_id or capture_id in seen or amount.get("currency_code") != "USD":
            raise PayPalError("Sandbox capture contains an unexpected payment record.")
        seen.add(capture_id)
        total += money(amount.get("value"))
    if not captures or total != money(record.plan["subtotal"]):
        raise PayPalError("Sandbox capture amount does not match the approved server plan.")


def _public_order(record: PlanRecord, order: dict) -> dict:
    captures = [
        {"id": capture.get("id"), "status": capture.get("status"), "amount": capture.get("amount")}
        for unit in order.get("purchase_units", [])
        for capture in unit.get("payments", {}).get("captures", [])
    ]
    return {"mode": "paypal_sandbox", "plan_id": record.plan_id,
            "order_id": order.get("id"), "status": order.get("status"),
            "approval_url": approval_url(order), "amount": f"{money(record.plan['subtotal']):.2f}",
            "currency": "USD", "approval_recorded": bool(record.approved_at),
            "captures": captures, "events": list(record.events), "synthetic_catalog": True,
            "plan": record.snapshot()}


class Handler(BaseHTTPRequestHandler):
    server_version = "MendCart/0.2"

    def log_message(self, fmt, *args):
        # Do not log payer return tokens or request payloads.
        print("MendCart request completed")

    def _origin(self):
        return getattr(self.server, "public_origin", public_origin())

    def _session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            cookie = SimpleCookie()
        proposed = cookie[COOKIE].value if COOKIE in cookie else None
        session, is_new = STORE.session(proposed)
        self.session_id = session
        if is_new:
            self.session_cookie = f"{COOKIE}={session}; Path=/; HttpOnly; SameSite=Lax"
            if self._origin().startswith("https://"):
                self.session_cookie += "; Secure"
        return session

    def _send(self, data, status_code=200, content_type="application/json; charset=utf-8"):
        payload = data.encode() if isinstance(data, str) else json.dumps(data, allow_nan=False).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        if getattr(self, "session_cookie", None):
            self.send_header("Set-Cookie", self.session_cookie)
        self.end_headers()
        self.wfile.write(payload)

    def _body(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid request length.") from None
        if size < 0 or size > 100_000:
            raise ValueError("Request body is too large.")
        body = json.loads(self.rfile.read(size) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object.")
        return body

    def _same_origin(self):
        origin = self.headers.get("Origin")
        if self.headers.get("Sec-Fetch-Site") == "cross-site" or (origin and origin.rstrip("/") != self._origin()):
            raise PermissionError("Use this app's browser session to approve checkout.")
        if self.headers.get("Host") != urlsplit(self._origin()).netloc:
            raise PermissionError("Request host does not match the configured MendCart origin.")

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            owner = self._session()
            if path == "/":
                return self._send((ROOT / "web" / "index.html").read_text(), content_type="text/html; charset=utf-8")
            if path == "/app.js":
                return self._send((ROOT / "web" / "app.js").read_text(), content_type="text/javascript; charset=utf-8")
            if path == "/favicon.ico":
                return self._send("", 204, content_type="image/x-icon")
            if path == "/api/status":
                return self._send(status())
            if path == "/api/health":
                return self._send({"ok": True, "mode": "local sandbox demo"})
            if path == "/api/catalog":
                return self._send({"items": public_catalog(), "synthetic": True, "as_of": CATALOG_AS_OF})
            if path.startswith("/api/plans/"):
                plan_path = path.removeprefix("/api/plans/")
                if plan_path.endswith("/preview"):
                    record = STORE.plan(owner, plan_path.removesuffix("/preview"), fresh=True)
                    with record.lock:
                        plan = _checkout_plan(record)
                        return self._send({"mode": "sandbox_preview", "status": "read_only_preview",
                                           "plan_id": record.plan_id, "amount": f"{money(plan['subtotal']):.2f}", "currency": "USD",
                                           "approval_recorded": bool(record.approved_at), "order_id": None, "approval_url": None,
                                           "message": "Unsubmitted local payload preview. No approval or provider request was recorded.",
                                           "order": order_payload(plan, record.plan_id, self._origin()), "events": list(record.events)})
                record = STORE.plan(owner, plan_path)
                return self._send(record.snapshot())
            if path.startswith("/api/paypal/orders/"):
                record = STORE.order(owner, path.removeprefix("/api/paypal/orders/"))
                with record.lock:
                    order = get_order(record.order["id"])
                    _verify_order(record, order)
                    record.event("sandbox_order_checked", status=order.get("status"))
                    return self._send(_public_order(record, order))
            return self._send({"detail": "Not found"}, 404)
        except PermissionError as exc:
            return self._send({"detail": str(exc)}, 403)
        except ValueError as exc:
            return self._send({"detail": str(exc)}, 422)
        except PayPalError as exc:
            return self._send({"detail": str(exc)}, 502)
        except Exception:
            return self._send({"detail": "The local demo could not complete this request."}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            self._same_origin()
            owner = self._session()
            body = self._body()
            if path == "/api/plan":
                try:
                    request = PlanRequest(**body)
                except TypeError:
                    raise ValueError("Request fields do not match the planning API.") from None
                plan = create_plan_sync(request)
                record = STORE.put(owner, plan, asdict(request))
                return self._send(record.snapshot())
            if path in {"/api/plans/approve", "/api/paypal/orders"}:
                plan_id = body.get("plan_id")
                if not isinstance(plan_id, str):
                    raise ValueError("A server-issued plan_id is required. Generate a plan first.")
                record = STORE.plan(owner, plan_id, fresh=True)
                with record.lock:
                    plan = _checkout_plan(record)
                    if body.get("human_approved") is True and not record.approved_at:
                        record.approved_at = timestamp()
                        record.event("plan_approved", amount=plan["subtotal"], currency="USD")
                    if not record.approved_at:
                        raise PermissionError("Review and approve this server plan before sandbox checkout.")
                    if path == "/api/plans/approve":
                        return self._send(record.snapshot())
                    if record.order:
                        return self._send(_public_order(record, record.capture or record.order))
                    if not sandbox_ready():
                        record.event("sandbox_preview_shown", amount=plan["subtotal"])
                        return self._send({"mode": "sandbox_preview", "status": "credentials_missing",
                                           "plan_id": record.plan_id, "amount": f"{money(plan['subtotal']):.2f}", "currency": "USD",
                                           "approval_recorded": True, "order_id": None, "approval_url": None,
                                           "message": "Plan approved locally. Sandbox credentials are needed for a provider order.",
                                           "order": order_payload(plan, record.plan_id, self._origin()), "events": list(record.events)})
                    order = create_order(plan, record.plan_id, record.create_request_id, self._origin())
                    approval_url(order)
                    STORE.bind_order(record, order)
                    return self._send(_public_order(record, order))
            if path == "/api/paypal/capture":
                order_id = body.get("order_id")
                if not isinstance(order_id, str):
                    raise ValueError("A stored sandbox order_id is required.")
                record = STORE.order(owner, order_id)
                with record.lock:
                    if record.capture:
                        result = _public_order(record, record.capture)
                        return self._send({**result, "capture": {"id": result["order_id"], "status": result["status"], "captures": result["captures"]}})
                    provider_order = get_order(order_id)
                    _verify_order(record, provider_order)
                    provider_status = provider_order.get("status")
                    record.event("payer_approval_verified", provider_status=provider_status)
                    if provider_status == "COMPLETED":
                        # Recover a previous capture whose HTTP response was lost.
                        _verify_capture(record, provider_order)
                        record.capture = provider_order
                        record.event("sandbox_capture_recovered", order_id=order_id)
                    elif provider_status == "APPROVED":
                        captured = capture_order(order_id, record.capture_request_id)
                        _verify_capture(record, captured)
                        record.capture = captured
                        record.event("sandbox_capture_result", order_id=order_id, status=captured.get("status"))
                    else:
                        raise PermissionError("The sandbox payer must approve this order in PayPal before capture.")
                    result = _public_order(record, record.capture)
                    return self._send({**result, "capture": {"id": result["order_id"], "status": result["status"], "captures": result["captures"]}})
            return self._send({"detail": "Not found"}, 404)
        except PermissionError as exc:
            return self._send({"detail": str(exc)}, 403)
        except ValueError as exc:
            return self._send({"detail": str(exc)}, 422)
        except PayPalError as exc:
            return self._send({"detail": str(exc)}, 502)
        except Exception:
            return self._send({"detail": "The local demo could not complete this request. No provider secrets are shown."}, 500)


def serve(host=None, port=None):
    host = host or os.getenv("MENDCART_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000")) if port is None else port
    httpd = ThreadingHTTPServer((host, port), Handler)
    origin_host = "127.0.0.1" if host == "0.0.0.0" else host
    httpd.public_origin = public_origin(f"http://{origin_host}:{httpd.server_port}")
    print(f"MendCart running at {httpd.public_origin}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
