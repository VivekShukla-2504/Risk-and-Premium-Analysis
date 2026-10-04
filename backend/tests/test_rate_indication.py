"""Hand-checked tests for the baseline credibility-weighted rate indication."""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import rate_indication_service as RI  # noqa: E402
from app.services.data_loader import clean_data  # noqa: E402

COLS = ["PolicyNumber", "CustomerID", "Gender", "Age", "PolicyType", "PolicyStartDate", "PolicyEndDate",
        "PremiumAmount", "CoverageAmount", "ClaimNumber", "ClaimDate", "ClaimAmount", "ClaimStatus"]

ROWS = [
    ["P1", "C1", "Male", "20", "Auto", "01-01-2024", "01-01-2025", "1000", "50000", "C1", "15-03-2024", "2000", "Settled"],
    ["P2", "C2", "Female", "30", "Auto", "01-01-2024", "01-01-2025", "800", "40000", "C2", "20-03-2024", "1000", "Pending"],
    ["P3", "C3", "Male", "40", "Auto", "01-01-2024", "01-01-2025", "600", "30000", "C3", None, "0", "Rejected"],
    ["P4", "C4", "Female", "50", "Home", "01-01-2024", "01-01-2025", "500", "20000", "C4", None, "0", "Rejected"],
    ["P5", "C5", "Male", "60", "Home", "01-01-2024", "01-01-2025", "400", "10000", "C5", "10-05-2024", "500", "Settled"],
    ["P6", "C6", "Female", "70", "Travel", "01-01-2024", "01-01-2025", "200", "10000", "C6", "05-05-2024", "1500", "Settled"],
]


def hand_df():
    return clean_data(
        pd.DataFrame(ROWS, columns=COLS).astype("string"),
        valuation_date="2025-01-01",
    )[0]


class RateIndication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = hand_df()

    def test_hand_calculated_portfolio_and_segment_indication(self):
        report = RI.rate_indication_report(self.df, 65)
        overall = report["overall"]
        auto = next(row for row in report["by_policy_type"] if row["segment"] == "Auto")

        self.assertEqual((overall["policies"], overall["claiming_policies"]), (6, 4))
        self.assertEqual(overall["incurred_claims"], 5000)
        self.assertEqual(overall["earned_premium"], 3500)
        self.assertAlmostEqual(overall["observed_pure_premium_per_policy"], 5000 / 6, places=2)
        self.assertIsNone(overall["credibility_factor"])
        self.assertIn("Unblended", overall["credibility_factor_note"])
        self.assertAlmostEqual(overall["indicated_earned_premium_per_policy"], (5000 / 6) / 0.65, places=2)
        self.assertAlmostEqual(
            overall["indicated_rate_change_pct"],
            (((5000 / 6) / 0.65) / (3500 / 6) - 1) * 100,
            places=2,
        )

        auto_z = (2 / 1082) ** 0.5
        expected_auto_pp = auto_z * 1000 + (1 - auto_z) * (5000 / 6)
        self.assertEqual((auto["policies"], auto["claiming_policies"]), (3, 2))
        self.assertAlmostEqual(auto["credibility_factor"], auto_z, places=6)
        self.assertAlmostEqual(auto["indicated_pure_premium_per_policy"], expected_auto_pp, places=2)
        self.assertAlmostEqual(auto["current_earned_premium_per_policy"], 800, places=2)

    def test_zero_claim_segment_borrows_filtered_portfolio_experience(self):
        rows = [row.copy() for row in ROWS]
        rows[4][10] = None
        rows[4][11] = "0"
        rows[4][12] = "Rejected"
        df = clean_data(
            pd.DataFrame(rows, columns=COLS).astype("string"),
            valuation_date="2025-01-01",
        )[0]
        report = RI.rate_indication_report(df, 65)
        home = next(row for row in report["by_policy_type"] if row["segment"] == "Home")
        portfolio_pp = 4500 / 6
        self.assertEqual(home["claiming_policies"], 0)
        self.assertEqual(home["credibility_factor"], 0)
        self.assertAlmostEqual(home["indicated_pure_premium_per_policy"], portfolio_pp, places=2)
        self.assertTrue(home["indication_available"])

    def test_no_claim_portfolio_does_not_produce_a_false_minus_100_percent_indication(self):
        rows = [row.copy() for row in ROWS]
        for row in rows:
            row[10] = None
            row[11] = "0"
            row[12] = "Rejected"
        no_claim_df = clean_data(
            pd.DataFrame(rows, columns=COLS).astype("string"),
            valuation_date="2025-01-01",
        )[0]
        report = RI.rate_indication_report(no_claim_df)
        self.assertFalse(report["available"])
        self.assertIsNone(report["overall"]["indicated_rate_change_pct"])
        self.assertIn("No payable claims", report["unavailable_reason"])
        self.assertTrue(all(not row["indication_available"] for row in report["by_policy_type"]))

    def test_one_claim_portfolio_is_unblended_and_does_not_claim_full_credibility(self):
        rows = [row.copy() for row in ROWS]
        for index in range(1, len(rows)):
            rows[index][10] = None
            rows[index][11] = "0"
            rows[index][12] = "Rejected"
        one_claim_df = clean_data(
            pd.DataFrame(rows, columns=COLS).astype("string"),
            valuation_date="2025-01-01",
        )[0]
        report = RI.rate_indication_report(one_claim_df)
        overall = report["overall"]
        auto = next(row for row in report["by_policy_type"] if row["segment"] == "Auto")

        self.assertEqual(overall["claiming_policies"], 1)
        self.assertIsNone(overall["credibility_factor"])
        self.assertIn("not applicable", overall["credibility_factor_note"])
        self.assertEqual(
            overall["indicated_pure_premium_per_policy"],
            overall["observed_pure_premium_per_policy"],
        )
        self.assertAlmostEqual(auto["credibility_factor"], (1 / 1082) ** 0.5, places=6)

    def test_empty_portfolio_has_no_overall_or_segment_indication(self):
        report = RI.rate_indication_report(self.df.iloc[0:0])
        self.assertFalse(report["available"])
        self.assertIsNone(report["overall"])
        self.assertEqual(report["by_policy_type"], [])
        self.assertIn("No policies", report["unavailable_reason"])

    def test_zero_current_earned_premium_has_no_percentage_indication(self):
        zero_earned = self.df.copy()
        zero_earned["EarnedPremium"] = 0.0
        report = RI.rate_indication_report(zero_earned)
        self.assertFalse(report["overall"]["indication_available"])
        self.assertIsNone(report["overall"]["indicated_rate_change_pct"])
        self.assertIn("Current earned premium", report["overall"]["unavailable_reason"])

    def test_full_credibility_caps_segment_factor_at_one(self):
        expanded = pd.concat([self.df] * 541, ignore_index=True)
        report = RI.rate_indication_report(expanded)
        self.assertEqual(report["overall"]["claiming_policies"], 2164)
        self.assertIsNone(report["overall"]["credibility_factor"])
        auto = next(row for row in report["by_policy_type"] if row["segment"] == "Auto")
        self.assertEqual(auto["claiming_policies"], 1082)
        self.assertEqual(auto["credibility_factor"], 1)

    def test_target_loss_ratio_boundaries_and_invalid_values(self):
        self.assertEqual(RI.rate_indication_report(self.df, 30)["assumptions"]["target_loss_ratio_pct"], 30)
        self.assertEqual(RI.rate_indication_report(self.df, 100)["assumptions"]["target_loss_ratio_pct"], 100)
        for target in (29.99, 100.01, float("nan"), float("inf")):
            with self.subTest(target=target), self.assertRaises(RI.RateIndicationError):
                RI.rate_indication_report(self.df, target)

    def test_report_discloses_formula_and_assumption_limits(self):
        report = RI.rate_indication_report(self.df)
        self.assertIn("sqrt(segment claiming policies / 1,082)", report["formulas"]["credibility_factor"])
        self.assertEqual(report["assumptions"]["target_loss_ratio_pct"], 65)
        self.assertTrue(any("not a Bühlmann model" in note for note in report["notes"]))
        self.assertIn("not a forecast", report["disclaimer"])


if __name__ == "__main__":
    unittest.main()
