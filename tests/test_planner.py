"""Held-out language and substantive cart-policy regression tests."""

import math
import io
import json
import os
import unittest
from unittest.mock import patch

from mendcart.catalog import CATALOG
from mendcart.planner import AgentPlan, PlanRequest, RequestedItem, _intent_model, create_plan_sync


class LearnedIntentTests(unittest.TestCase):
    # None of these exact strings appears in the training corpus.
    CASES = [
        ("The circulation pump dribbles at the gasket", "pump"),
        ("Our pump shaft is dripping; which seal should we get", "pump"),
        ("Restore two leaking water pumps at our repair bench", "pump"),
        ("The water pump assembly has failed beyond repair", "pump"),
        ("Eight protected 18650 cells for a rechargeable lantern", "battery"),
        ("Six battery cells to rebuild the exhausted pack", "battery"),
        ("Supply three packs of tested reclaimed batteries", "battery"),
        ("Twelve lithium cells for the workshop portable light", "battery"),
        ("A set of screwdrivers and pliers for our repair station", "tools"),
        ("Our technicians require two insulated tool sets", "tools"),
        ("Choose an appliance servicing toolkit for the workbench", "tools"),
        ("Find maintenance tools for the household appliance bench", "tools"),
        ("Purchase a quantum telescope with a camera", "unsupported"),
        ("We want groceries and office chairs", "unsupported"),
        ("Order a gaming laptop for video editing", "unsupported"),
        ("Supply a drone and television for the team", "unsupported"),
    ]

    def test_held_out_intent_classification(self):
        for text, expected in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(_intent_model().classify(text)["intent"], expected)

    def test_inference_exposes_learned_evidence(self):
        inference = _intent_model().classify("A worn pump gasket is dripping")
        self.assertTrue(inference["accepted"])
        self.assertGreater(inference["margin"], 0.035)
        self.assertTrue(inference["matches"])
        self.assertGreater(inference["matches"][0]["similarity"], 0)
        self.assertGreater(len(_intent_model().idf), 100)


class ConstraintPlannerTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"OPENAI_BASE_URL": "", "OPENAI_API_KEY": "", "OPENAI_MODEL": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def plan(self, text, budget=120, **kwargs):
        return create_plan_sync(PlanRequest(text, budget, **kwargs))

    def skus(self, plan):
        return [row["sku"] for row in plan["items"]]

    def test_repair_and_replacement_are_compared_not_both_bought(self):
        plan = self.plan("Our circulation pump dribbles at the gasket; fix it under $120")
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["PUMP-SEAL-KIT"])
        self.assertEqual({row["sku"] for row in plan["candidates"]}, {"PUMP-SEAL-KIT", "PUMP-REPLACE"})
        self.assertEqual(sum(row["selected"] for row in plan["candidates"]), 1)

    def test_battery_fallback_is_not_purchased_simultaneously(self):
        plan = self.plan("Source eight tested 18650 cells")
        self.assertEqual(self.skus(plan), ["BAT-RECLAIM-4"])
        self.assertEqual(plan["items"][0]["quantity"], 2)
        self.assertEqual(plan["subtotal"], 22)

    def test_pack_rounding_discloses_surplus(self):
        plan = self.plan("Need six battery cells")
        self.assertEqual(plan["items"][0]["quantity"], 2)
        self.assertIn("supply 8 cells", plan["requirements"][0]["quantity_note"])

    def test_explicit_pack_quantity(self):
        plan = self.plan("Supply three packs of tested reclaimed batteries")
        self.assertEqual(plan["items"][0]["quantity"], 3)

    def test_product_identifier_is_not_a_quantity(self):
        plan = self.plan("Need 18650 cells for a rechargeable light")
        self.assertEqual(plan["items"][0]["quantity"], 1)

    def test_multiple_goals_quantity_and_negation(self):
        plan = self.plan("Repair two leaking water pumps and buy eight cells, no tools")
        self.assertTrue(plan["policy_passed"])
        self.assertEqual([(row["sku"], row["quantity"]) for row in plan["items"]], [("PUMP-SEAL-KIT", 2), ("BAT-RECLAIM-4", 2)])
        self.assertEqual(plan["subtotal"], 70)

    def test_new_only_condition_excludes_reclaimed_cells(self):
        plan = self.plan("Eight protected 18650 cells, only new please")
        self.assertEqual(self.skus(plan), ["BAT-18650-4"])
        self.assertIn("BAT-RECLAIM-4", plan["exclusions"])

    def test_negated_condition_does_not_remove_positive_goal(self):
        plan = self.plan("I need 8 cells, do not use reclaimed cells")
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["BAT-18650-4"])

    def test_reclaimed_only_cannot_fall_back_to_new(self):
        plan = self.plan("Need eight cells, only reclaimed cells", allowed_suppliers=["greenloop-demo"])
        self.assertFalse(plan["policy_passed"])
        self.assertFalse(plan["items"])

    def test_no_new_cells_does_not_accidentally_forbid_reclaimed(self):
        plan = self.plan("Need eight cells, no new cells")
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["BAT-RECLAIM-4"])

    def test_negated_tools_do_not_create_an_extra_purchase(self):
        plan = self.plan("Repair the leaking water pump; I don't need tools")
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["PUMP-SEAL-KIT"])

    def test_replacement_selected_only_when_requested(self):
        plan = self.plan("The water pump cannot be repaired; must replace the assembly")
        self.assertEqual(self.skus(plan), ["PUMP-REPLACE"])
        self.assertEqual(plan["subtotal"], 94)

    def test_explicit_replacement_and_repair_kit_negation(self):
        plan = self.plan("Replace the water pump. Do not buy a repair kit.", repair_first=True)
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["PUMP-REPLACE"])
        self.assertEqual(plan["subtotal"], 94)

    def test_explicit_replacement_outranks_repair_first_preference(self):
        plan = self.plan("Replace my leaking water pump", repair_first=True)
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["PUMP-REPLACE"])

    def test_repair_kit_prohibition_selects_replacement(self):
        plan = self.plan("The water pump is broken; do not buy a repair kit", repair_first=True)
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["PUMP-REPLACE"])

    def test_replacing_a_pump_seal_still_selects_repair_kit(self):
        plan = self.plan("Replace the water pump seal", repair_first=True)
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["PUMP-SEAL-KIT"])

    def test_replacement_prohibition(self):
        plan = self.plan("The pump drips but do not buy a replacement")
        self.assertEqual(self.skus(plan), ["PUMP-SEAL-KIT"])
        self.assertIn("PUMP-REPLACE", plan["exclusions"])

    def test_supplier_policy_selects_eligible_fallback(self):
        plan = self.plan("Eight 18650 cells", allowed_suppliers=["greenloop-demo"])
        self.assertTrue(plan["policy_passed"])
        self.assertEqual(self.skus(plan), ["BAT-18650-4"])

    def test_named_supplier_in_prompt_is_honored(self):
        plan = self.plan("Need eight cells, only GreenLoop")
        self.assertEqual(self.skus(plan), ["BAT-18650-4"])

    def test_budget_in_prompt_cannot_be_ignored(self):
        plan = self.plan("Repair my pump under $20", budget=120)
        self.assertFalse(plan["policy_passed"])
        self.assertEqual(plan["budget_cap"], 20)
        self.assertIn("exceeds", plan["policy_findings"][0])

    def test_structured_budget_is_never_expanded_by_text(self):
        plan = self.plan("Repair my pump, budget 200", budget=20)
        self.assertFalse(plan["policy_passed"])
        self.assertEqual(plan["budget_cap"], 20)

    def test_no_partial_cart_passes_when_one_goal_has_no_supplier(self):
        plan = self.plan("Repair a water pump and source eight cells", allowed_suppliers=["fixfirst-demo"])
        self.assertFalse(plan["policy_passed"])
        self.assertFalse(plan["items"])

    def test_unknown_second_goal_does_not_silently_disappear(self):
        with self.assertRaises(ValueError):
            self.plan("Fix the water pump and buy a telescope under $30")

    def test_quantity_out_of_bounds_is_not_silently_clamped(self):
        with self.assertRaises(ValueError):
            self.plan("Supply twenty-four 18650 cells")
        with self.assertRaises(ValueError):
            self.plan("Supply 24 battery cells")
        with self.assertRaises(ValueError):
            self.plan("Supply one hundred battery cells")
        with self.assertRaises(ValueError):
            self.plan("Need -2 battery cells")

    def test_all_catalog_evidence_is_explicitly_synthetic(self):
        plan = self.plan("Repair my leaking water pump")
        self.assertTrue(all(row["synthetic"] and row["evidence_ids"] for row in plan["items"]))
        self.assertIn("Fictional", plan["items"][0]["compatibility"])
        self.assertEqual(plan["planner"]["engine"], "local-tfidf-knn-v1")

    def test_invalid_numeric_budgets_fail_before_planning(self):
        for value in (True, math.nan, math.inf, -1, 0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PlanRequest("Repair water pump", value)

    def test_external_model_cannot_buy_both_alternatives(self):
        model = AgentPlan("x", [RequestedItem("PUMP-SEAL-KIT"), RequestedItem("PUMP-REPLACE")], "x", requirements=[{"intent":"pump", "quantity":1}])
        with patch("mendcart.planner._model_plan", return_value=model):
            plan = self.plan("Repair a water pump")
        self.assertFalse(plan["policy_passed"])
        self.assertTrue(any("simultaneous alternatives" in finding for finding in plan["policy_findings"]))

    def test_external_model_cannot_buy_unrequested_category(self):
        model = AgentPlan("x", [RequestedItem("PUMP-SEAL-KIT"), RequestedItem("TOOL-MULTI")], "x", requirements=[{"intent":"pump", "quantity":1}])
        with patch("mendcart.planner._model_plan", return_value=model):
            plan = self.plan("Repair a water pump")
        self.assertFalse(plan["policy_passed"])

    def test_structured_adapter_rejects_fractional_quantity(self):
        body = {"choices": [{"message": {"content": json.dumps({"summary":"x", "reasoning":"x", "items":[{"sku":"BAT-18650-4", "quantity":2.5}]})}}]}
        with patch.dict(os.environ, {"OPENAI_BASE_URL":"https://model.example/v1", "OPENAI_API_KEY":"test-only", "OPENAI_MODEL":"test-model"}), patch("mendcart.planner.urlopen", return_value=io.BytesIO(json.dumps(body).encode())):
            with self.assertRaises(ValueError):
                self.plan("Need eight new 18650 cells")

    def test_structured_adapter_cannot_override_condition_exclusion(self):
        body = {"choices": [{"message": {"content": json.dumps({"summary":"x", "reasoning":"x", "items":[{"sku":"BAT-RECLAIM-4", "quantity":2}]})}}]}
        with patch.dict(os.environ, {"OPENAI_BASE_URL":"https://model.example/v1", "OPENAI_API_KEY":"test-only", "OPENAI_MODEL":"test-model"}), patch("mendcart.planner.urlopen", return_value=io.BytesIO(json.dumps(body).encode())):
            plan = self.plan("Need eight new 18650 cells")
        self.assertFalse(plan["policy_passed"])
        self.assertTrue(any("request-excluded" in finding for finding in plan["policy_findings"]))

    def test_inventory_fallback_is_considered(self):
        altered = [{**row, "stock": 0} if row["sku"] == "BAT-RECLAIM-4" else dict(row) for row in CATALOG]
        with patch("mendcart.planner.CATALOG", altered):
            plan = self.plan("Eight battery cells")
        self.assertEqual(self.skus(plan), ["BAT-18650-4"])
        self.assertTrue(plan["policy_passed"])


if __name__ == "__main__":
    unittest.main()
