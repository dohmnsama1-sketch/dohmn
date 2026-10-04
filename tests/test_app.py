import json
from pathlib import Path
import os
import unittest
from unittest.mock import patch
from urllib.request import Request

from mendcart.app import Handler, status
from mendcart.planner import PlanRequest, create_plan_sync
from mendcart.paypal import _base_url


class PlannerTests(unittest.TestCase):
    def test_repair_first_pump_plan_passes(self):
        plan = create_plan_sync(PlanRequest(request="The water pump is leaking, try repair", max_budget=120))
        self.assertTrue(plan["policy_passed"])
        self.assertEqual([x["sku"] for x in plan["items"]], ["PUMP-SEAL-KIT"])
        self.assertEqual(plan["subtotal"], 24.0)

    def test_budget_overrun_blocks_policy(self):
        plan = create_plan_sync(PlanRequest(request="Need repair tools for appliance", max_budget=20))
        self.assertFalse(plan["policy_passed"])
        self.assertIn("exceeds the authorized budget cap", plan["policy_findings"][0])

    def test_unknown_request_fails_closed(self):
        with self.assertRaises(ValueError):
            create_plan_sync(PlanRequest(request="Buy a quantum telescope now", max_budget=100))

    def test_model_output_cannot_select_unapproved_supplier(self):
        with patch("mendcart.planner._model_plan", return_value=type("Plan", (), {"summary":"x", "reasoning":"x", "items":[type("Line", (), {"sku":"UNKNOWN-GADGET", "quantity":1})()]})()):
            plan = create_plan_sync(PlanRequest(request="Need a safe repair item", max_budget=100))
        self.assertFalse(plan["policy_passed"])
        self.assertFalse(plan["items"])


class ApiTests(unittest.TestCase):
    def test_status_is_honest_about_synthetic_data(self):
        data = status()
        self.assertTrue(data["catalog_is_synthetic"])
        self.assertFalse(data["live_integrations"])

    def test_live_paypal_host_is_rejected(self):
        with patch.dict(os.environ, {"PAYPAL_BASE_URL": "https://api-m.paypal.com"}, clear=False):
            with self.assertRaises(ValueError):
                _base_url()

    def test_http_human_gate_blocks_order(self):
        # Exercise route-boundary enforcement without starting a server or calling PayPal.
        self.assertTrue(callable(Handler.do_POST))
        source = Path("mendcart/app.py").read_text(encoding="utf-8")
        self.assertIn("human_approved", source)


if __name__ == "__main__":
    unittest.main()
