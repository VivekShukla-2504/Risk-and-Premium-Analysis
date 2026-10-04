"""Tests for the Baseline / Optimistic / Stress / Custom comparison (hand-calculated on a 6-policy portfolio)."""
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import scenario_service as S  # noqa: E402
from app.services.data_loader import clean_data, load_clean_dataset  # noqa: E402

COLS = ["PolicyNumber", "CustomerID", "Gender", "Age", "PolicyType", "PolicyStartDate", "PolicyEndDate",
        "PremiumAmount", "CoverageAmount", "ClaimNumber", "ClaimDate", "ClaimAmount", "ClaimStatus"]


def row(n, g, age, t, prem, cov, status, amt, cd):
    return [f"P{n}", f"C{n}", g, str(age), t, "01-01-2024", "01-01-2025", str(prem), str(cov), f"C{n}", cd, str(amt), status]


# 6 policies: 4 claims, incurred 5000, earned premium 3500 (fully earned at 2025-01-01)
ROWS = [row(1, "Male", 20, "Auto", 1000, 50000, "Settled", 2000, "15-03-2024"),
        row(2, "Female", 30, "Auto", 800, 40000, "Pending", 1000, "20-03-2024"),
        row(3, "Male", 40, "Auto", 600, 30000, "Rejected", 0, None),
        row(4, "Female", 50, "Home", 500, 20000, "Rejected", 0, None),
        row(5, "Male", 60, "Home", 400, 10000, "Settled", 500, "10-05-2024"),
        row(6, "Female", 70, "Travel", 200, 10000, "Settled", 1500, "05-05-2024")]


def hand_df():
    return clean_data(pd.DataFrame(ROWS, columns=COLS).astype("string"), valuation_date="2025-01-01")[0]


class Compare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = hand_df()
        cls.custom = S.ScenarioInputs(frequency_change_pct=20, severity_change_pct=-10, inflation_pct=5,
                                      premium_adjustment_pct=10, expense_ratio_pct=30, target_loss_ratio_pct=60)
        cls.res = S.compare_scenarios(cls.df, cls.custom)
        cls.by = {s["key"]: s for s in cls.res["scenarios"]}

    def test_four_scenarios_in_order(self):
        self.assertEqual([s["key"] for s in self.res["scenarios"]], ["baseline", "optimistic", "stress", "custom"])
        self.assertEqual([s["is_preset"] for s in self.res["scenarios"]], [True, True, True, False])

    def test_baseline_reproduces_observed_experience(self):
        r = self.by["baseline"]["results"]
        self.assertEqual(r["baseline_claim_cost"], 5000.00)
        self.assertEqual(r["adjusted_expected_claim_cost"], 5000.00)
        self.assertAlmostEqual(r["adjusted_claim_frequency"], 4 / 6, places=6)
        self.assertEqual(r["adjusted_claim_severity"], 1250.00)
        self.assertEqual(r["adjusted_premium"], 3500.00)
        self.assertAlmostEqual(r["adjusted_loss_ratio"], 5000 / 3500, places=6)
        self.assertEqual(self.by["baseline"]["change_vs_baseline"]["loss_ratio_points"], 0)

    def test_optimistic_by_hand(self):
        # freq -10%, sev -5%, inflation +2%, premium +5%
        r = self.by["optimistic"]["results"]
        cost = 5000 * 0.90 * 0.95 * 1.02
        self.assertAlmostEqual(r["adjusted_expected_claim_cost"], cost, delta=0.01)
        self.assertAlmostEqual(r["adjusted_claim_frequency"], (4 / 6) * 0.9, places=6)
        self.assertAlmostEqual(r["adjusted_claim_severity"], 1250 * 0.95 * 1.02, delta=0.01)
        self.assertAlmostEqual(r["adjusted_premium"], 3500 * 1.05, delta=0.01)
        self.assertAlmostEqual(r["adjusted_loss_ratio"], cost / (3500 * 1.05), places=5)

    def test_stress_by_hand(self):
        # freq +15%, sev +10%, inflation +8%, premium 0%
        r = self.by["stress"]["results"]
        cost = 5000 * 1.15 * 1.10 * 1.08
        self.assertAlmostEqual(r["adjusted_expected_claim_cost"], cost, delta=0.01)
        self.assertAlmostEqual(r["adjusted_loss_ratio"], cost / 3500, places=5)
        self.assertAlmostEqual(self.by["stress"]["change_vs_baseline"]["loss_ratio_points"], (cost / 3500 - 5000 / 3500) * 100, places=3)

    def test_custom_uses_request_values_and_orders_sensibly(self):
        r = self.by["custom"]["results"]
        cost = 5000 * 1.20 * 0.90 * 1.05
        self.assertAlmostEqual(r["adjusted_expected_claim_cost"], cost, delta=0.01)
        self.assertAlmostEqual(r["adjusted_premium"], 3850.00, delta=0.01)
        lr = {k: v["results"]["adjusted_loss_ratio"] for k, v in self.by.items()}
        self.assertLess(lr["optimistic"], lr["baseline"])
        self.assertGreater(lr["stress"], lr["baseline"])

    def test_shared_assumptions_apply_to_all_scenarios(self):
        for s in self.res["scenarios"]:
            self.assertEqual(s["inputs"]["expense_ratio_pct"], 30)
            self.assertAlmostEqual(s["results"]["expense_ratio"], 0.30, places=6)
        self.assertEqual(self.res["shared_assumptions"]["expense_ratio_pct"], 30)
        self.assertIn("Assumed", self.res["shared_assumptions"]["expense_ratio_note"])

    def test_margin_and_break_even(self):
        s = self.by["stress"]
        cost = 5000 * 1.15 * 1.10 * 1.08
        self.assertAlmostEqual(s["results"]["underwriting_margin"], 1 - cost / 3500 - 0.30, places=5)
        self.assertFalse(s["is_profitable"])
        self.assertAlmostEqual(s["premium_change_to_break_even_pct"], (cost / 0.70 / 3500 - 1) * 100, places=1)

    def test_steps_match_results_and_explain_each_calculation(self):
        for s in self.res["scenarios"]:
            steps = s["steps"]
            self.assertEqual([x["label"] for x in steps], [
                "Baseline claim cost", "Adjusted claim frequency", "Adjusted claim severity", "Adjusted expected claim cost",
                "Adjusted premium", "Adjusted loss ratio", "Illustrative underwriting margin"])
            for x in steps:
                for field in ("formula", "substitution", "explanation"):
                    self.assertTrue(x[field], f"{s['key']} {x['label']} {field}")
            r = s["results"]
            vals = [x["value"] for x in steps]
            self.assertAlmostEqual(vals[0], r["baseline_claim_cost"], delta=0.01)
            self.assertAlmostEqual(vals[1], r["adjusted_claim_frequency"], places=6)
            self.assertAlmostEqual(vals[2], r["adjusted_claim_severity"], delta=0.01)
            self.assertAlmostEqual(vals[3], r["adjusted_expected_claim_cost"], delta=0.01)
            self.assertAlmostEqual(vals[4], r["adjusted_premium"], delta=0.01)
            self.assertAlmostEqual(vals[5], r["adjusted_loss_ratio"], places=6)
            self.assertAlmostEqual(vals[6], r["underwriting_margin"], places=6)

    def test_substitution_text_shows_the_adjustments(self):
        text = {x["label"]: x["substitution"] for x in self.by["optimistic"]["steps"]}
        self.assertIn("(1 - 10.0%)", text["Adjusted claim frequency"])
        self.assertIn("(1 - 5.0%)", text["Adjusted claim severity"])
        self.assertIn("(1 + 2.0%)", text["Adjusted claim severity"])
        self.assertIn("(1 + 5.0%)", text["Adjusted premium"])
        self.assertTrue(text["Baseline claim cost"].startswith("6 x 66.67%"))

    def test_presets_respect_limits_and_are_labelled(self):
        for p in S.PRESETS:
            S.ScenarioInputs(**p["inputs"]).validate()
        self.assertIn("not estimated from the data", S.PRESET_NOTE)
        self.assertIn("not a prediction", self.res["disclaimer"])
        self.assertEqual(self.res["baseline"]["policies"], 6)

    def test_invalid_and_empty_inputs(self):
        with self.assertRaises(S.ScenarioError):
            S.compare_scenarios(self.df, S.ScenarioInputs(frequency_change_pct=25))
        with self.assertRaises(S.ScenarioError):
            S.compare_scenarios(self.df.iloc[0:0], S.ScenarioInputs())
        with self.assertRaises(S.ScenarioError):
            S.compare_scenarios(self.df[self.df["ClaimStatus"] == "Rejected"], S.ScenarioInputs())

    def test_frequency_incidence_boundary_and_infeasible_shocks(self):
        five_claim_rows = [list(r) for r in ROWS]
        five_claim_rows[2] = row(3, "Male", 40, "Auto", 600, 30000, "Settled", 700, "12-12-2024")
        five_claim_df = clean_data(pd.DataFrame(five_claim_rows, columns=COLS).astype("string"),
                                   valuation_date="2025-01-01")[0]
        at_bound = S.compute_scenario(five_claim_df, S.ScenarioInputs(frequency_change_pct=20))
        self.assertEqual(at_bound["scenario"]["claim_frequency"], 1.0)

        all_claim_rows = [list(r) for r in five_claim_rows]
        all_claim_rows[3] = row(4, "Female", 50, "Home", 500, 20000, "Settled", 900, "14-12-2024")
        all_claim_df = clean_data(pd.DataFrame(all_claim_rows, columns=COLS).astype("string"),
                                  valuation_date="2025-01-01")[0]
        with self.assertRaisesRegex(S.ScenarioError, "100% maximum"):
            S.compute_scenario(all_claim_df, S.ScenarioInputs(frequency_change_pct=20))

        compared = S.compare_scenarios(all_claim_df, S.ScenarioInputs())
        by_key = {scenario["key"]: scenario for scenario in compared["scenarios"]}
        self.assertIsNotNone(by_key["baseline"]["results"])
        self.assertIsNotNone(by_key["custom"]["results"])
        self.assertIsNone(by_key["stress"]["results"])
        self.assertIn("100% maximum", by_key["stress"]["validation_error"])

    def test_json_safe(self):
        json.dumps(self.res, allow_nan=False)

    def test_real_dataset_headline_numbers(self):
        df, _ = load_clean_dataset(Path(__file__).resolve().parents[1] / "data" / "InsuranceData.csv")
        res = S.compare_scenarios(df, S.ScenarioInputs())
        by = {s["key"]: s["results"] for s in res["scenarios"]}
        self.assertAlmostEqual(by["baseline"]["adjusted_loss_ratio"], 2.8298, places=4)
        self.assertAlmostEqual(by["baseline"]["baseline_claim_cost"], 16904295.27, delta=0.5)
        self.assertLess(by["optimistic"]["adjusted_loss_ratio"], by["baseline"]["adjusted_loss_ratio"])
        self.assertGreater(by["stress"]["adjusted_loss_ratio"], by["baseline"]["adjusted_loss_ratio"])


if __name__ == "__main__":
    unittest.main()
