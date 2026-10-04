"""
Unit tests for analytics_service.

Part 1 uses a 6-policy portfolio small enough to verify BY HAND (see comments).
Part 2 checks identities and known totals on the real dataset.
"""
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import analytics_service as A  # noqa: E402
from app.services.data_loader import clean_data, load_clean_dataset, read_cleaned_csv  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
COLS = ["PolicyNumber", "CustomerID", "Gender", "Age", "PolicyType", "PolicyStartDate", "PolicyEndDate",
        "PremiumAmount", "CoverageAmount", "ClaimNumber", "ClaimDate", "ClaimAmount", "ClaimStatus"]


def row(n, gender, age, ptype, prem, cov, status, amount, claim_date):
    return [f"P{n}", f"C{n}", gender, str(age), ptype, "01-01-2024", "01-01-2025", str(prem), str(cov),
            f"C{n}", claim_date, str(amount), status]


# Hand-calculated portfolio (all policies run 2024-01-01 -> 2025-01-01, fully earned at 2025-01-01)
#  P1 Auto   M 20  prem 1000 cov 50000 Settled 2000  claim 15-03-2024
#  P2 Auto   F 30  prem  800 cov 40000 Pending 1000  claim 20-03-2024
#  P3 Auto   M 40  prem  600 cov 30000 Rejected 0
#  P4 Home   F 50  prem  500 cov 20000 Rejected 0
#  P5 Home   M 60  prem  400 cov 10000 Settled  500  claim 10-05-2024
#  P6 Travel F 70  prem  200 cov 10000 Settled 1500  claim 05-05-2024
ROWS = [
    row(1, "Male", 20, "Auto", 1000, 50000, "Settled", 2000, "15-03-2024"),
    row(2, "Female", 30, "Auto", 800, 40000, "Pending", 1000, "20-03-2024"),
    row(3, "Male", 40, "Auto", 600, 30000, "Rejected", 0, None),
    row(4, "Female", 50, "Home", 500, 20000, "Rejected", 0, None),
    row(5, "Male", 60, "Home", 400, 10000, "Settled", 500, "10-05-2024"),
    row(6, "Female", 70, "Travel", 200, 10000, "Settled", 1500, "05-05-2024"),
]


def build(rows=ROWS, valuation="2025-01-01"):
    df, _ = clean_data(pd.DataFrame(rows, columns=COLS).astype("string"), valuation_date=valuation)
    return df


class HandCalculated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = build()
        cls.m = A.portfolio_summary(cls.df)["metrics"]

    def test_totals(self):
        m = self.m
        self.assertEqual(m["policies"], 6)
        self.assertEqual(m["claiming_policies"], 4)          # P1, P2, P5, P6
        self.assertEqual((m["settled_claims"], m["pending_claims"]), (3, 1))
        self.assertEqual(m["total_premium"], 3500.00)        # 1000+800+600+500+400+200
        self.assertEqual(m["total_earned_premium"], 3500.00) # fully earned
        self.assertEqual(m["total_coverage"], 160000.00)
        self.assertEqual(m["total_claim_amount"], 5000.00)   # 2000+1000+500+1500
        self.assertEqual(m["total_paid_amount"], 4000.00)    # excludes Pending 1000
        self.assertEqual(m["total_outstanding_amount"], 1000.00)

    def test_frequency_severity_pure_premium(self):
        m = self.m
        self.assertAlmostEqual(m["claim_frequency"], 4 / 6, places=6)
        self.assertEqual(m["claim_severity"], 1250.00)       # 5000 / 4 (zero-claim policies excluded)
        self.assertAlmostEqual(m["pure_premium"], 5000 / 6, places=2)   # 0.6667 x 1250
        self.assertEqual(m["average_premium"], round(3500 / 6, 2))
        self.assertEqual(m["average_coverage"], round(160000 / 6, 2))

    def test_pure_premium_identity(self):
        m = self.m
        self.assertAlmostEqual(m["claim_frequency"] * m["claim_severity"], m["total_claim_amount"] / m["policies"], places=2)

    def test_claim_to_coverage(self):
        m = self.m
        # per-claim: .04, .025, .05, .15 -> mean .06625
        self.assertAlmostEqual(m["claim_to_coverage_ratio"], 0.06625, places=6)
        self.assertAlmostEqual(m["claim_to_coverage_aggregate"], 5000 / 110000, places=6)  # coverage of claimants only
        self.assertAlmostEqual(m["max_claim_to_coverage"], 0.15, places=6)
        self.assertAlmostEqual(m["coverage_utilization"], 5000 / 160000, places=6)

    def test_loss_ratios(self):
        self.assertAlmostEqual(self.m["loss_ratio"], 5000 / 3500, places=6)
        self.assertAlmostEqual(self.m["paid_loss_ratio"], 4000 / 3500, places=6)
        self.assertLess(self.m["paid_loss_ratio"], self.m["loss_ratio"])

    def test_loss_ratio_uses_earned_not_written_premium(self):
        df = build(valuation="2024-07-01")                    # ~half the term elapsed
        m = A.portfolio_summary(df)["metrics"]
        self.assertAlmostEqual(m["total_earned_premium"], 3500 * 182 / 366, delta=0.02)
        self.assertEqual(m["total_premium"], 3500.00)
        self.assertGreater(m["loss_ratio"], 5000 / 3500)      # smaller denominator -> higher ratio

    def test_exposure(self):
        self.assertAlmostEqual(self.m["exposure_policy_years"], 6 * 366 / 365.25, places=4)

    def test_confidence_interval_contains_estimate(self):
        ci = A.portfolio_summary(self.df)["confidence_intervals_95"]["claim_frequency"]
        self.assertLess(ci["low"], 4 / 6)
        self.assertGreater(ci["high"], 4 / 6)

    def test_policy_type_segments(self):
        seg = {r["segment"]: r for r in A.policy_type_analytics(self.df)["segments"]}
        self.assertEqual(seg["Auto"]["policies"], 3)
        self.assertEqual(seg["Auto"]["claiming_policies"], 2)
        self.assertEqual(seg["Auto"]["total_claim_amount"], 3000.00)
        self.assertEqual(seg["Auto"]["claim_severity"], 1500.00)
        self.assertAlmostEqual(seg["Auto"]["loss_ratio"], 3000 / 2400, places=6)
        self.assertAlmostEqual(seg["Home"]["loss_ratio"], 500 / 900, places=6)
        self.assertAlmostEqual(seg["Travel"]["loss_ratio"], 1500 / 200, places=6)
        self.assertAlmostEqual(seg["Auto"]["frequency_index_vs_portfolio"], (2 / 3) / (4 / 6), places=6)

    def test_segments_add_up_to_portfolio(self):
        for fn in (A.policy_type_analytics, A.age_band_analytics, A.gender_analytics):
            segs = fn(self.df)["segments"]
            self.assertEqual(sum(s["policies"] for s in segs), 6)
            self.assertEqual(sum(s["claiming_policies"] for s in segs), 4)
            self.assertAlmostEqual(sum(s["total_claim_amount"] for s in segs), 5000.00, places=2)
            self.assertAlmostEqual(sum(s["total_premium"] for s in segs), 3500.00, places=2)

    def test_age_band_includes_empty_band_without_error(self):
        segs = A.age_band_analytics(self.df)["segments"]
        self.assertEqual([s["segment"] for s in segs], A.AGE_BAND_LABELS)
        empty = segs[-1]                                      # 76+
        self.assertEqual(empty["policies"], 0)
        self.assertIsNone(empty["claim_frequency"])
        self.assertIsNone(empty["loss_ratio"])

    def test_gender_split(self):
        seg = {r["segment"]: r for r in A.gender_analytics(self.df)["segments"]}
        self.assertEqual(seg["Male"]["claiming_policies"], 2)    # P1, P5
        self.assertEqual(seg["Female"]["claiming_policies"], 2)  # P2, P6

    def test_claim_status(self):
        rows = {r["status"]: r for r in A.claim_status_analytics(self.df)["statuses"]}
        self.assertEqual(rows["Settled"]["policies"], 3)
        self.assertEqual(rows["Settled"]["paid_amount"], 4000.00)
        self.assertEqual(rows["Pending"]["outstanding_amount"], 1000.00)
        self.assertEqual(rows["Rejected"]["incurred_amount"], 0.0)
        self.assertEqual(rows["Rejected"]["claim_records"], 0)
        self.assertAlmostEqual(rows["Settled"]["share_of_incurred"] + rows["Pending"]["share_of_incurred"], 1.0, places=6)

    def test_monthly(self):
        months = {r["month"]: r for r in A.monthly_claim_analytics(self.df)["months"]}
        self.assertEqual(list(months), ["2024-03", "2024-04", "2024-05"])   # April has zero claims but is kept
        self.assertEqual(months["2024-03"]["claims"], 2)
        self.assertEqual(months["2024-03"]["incurred_amount"], 3000.00)
        self.assertEqual(months["2024-04"]["claims"], 0)
        self.assertEqual(months["2024-05"]["incurred_amount"], 2000.00)
        self.assertEqual(months["2024-03"]["policies_in_force"], 6)
        self.assertAlmostEqual(months["2024-03"]["exposure_policy_months"], 6.0, places=2)
        self.assertAlmostEqual(months["2024-03"]["claims_per_100_policy_months"], 2 / 6 * 100, places=4)
        self.assertIsNone(months["2024-04"]["average_severity"])


class EdgeCases(unittest.TestCase):
    def test_empty_dataframe_does_not_raise(self):
        empty = build().iloc[0:0]
        m = A.portfolio_summary(empty)["metrics"]
        self.assertEqual(m["policies"], 0)
        for key in ("claim_frequency", "claim_severity", "pure_premium", "loss_ratio", "average_premium"):
            self.assertIsNone(m[key], key)
        self.assertEqual(A.monthly_claim_analytics(empty)["months"], [])

    def test_no_claims_gives_zero_frequency_and_undefined_severity(self):
        df = build().query("ClaimStatus == 'Rejected'")
        m = A.portfolio_summary(df)["metrics"]
        self.assertEqual(m["claim_frequency"], 0.0)
        self.assertIsNone(m["claim_severity"])      # no claims -> severity undefined, not 0
        self.assertEqual(m["pure_premium"], 0.0)
        self.assertEqual(m["loss_ratio"], 0.0)

    def test_bad_inputs_rejected(self):
        with self.assertRaises(ValueError):
            A.segment_analytics(build(), "NotAColumn")
        with self.assertRaises(ValueError):
            A.total_claim_amount(build(), basis="bogus")

    def test_wilson_interval(self):
        self.assertEqual(A.wilson_interval(0, 0), (None, None))
        lo, hi = A.wilson_interval(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)
        self.assertEqual(A.wilson_interval(0, 10)[0], 0.0)

    def test_credibility_capped_at_one(self):
        self.assertEqual(A._derive({**A._sums(build()), "claims": 5000})["credibility_z"], 1.0)


class DocumentationCompleteness(unittest.TestCase):
    def test_every_metric_has_full_definition(self):
        metrics = A.portfolio_summary(build())["metrics"]
        for key in metrics:
            self.assertIn(key, A.METRIC_DEFINITIONS, f"{key} has no definition")
        for key, d in A.METRIC_DEFINITIONS.items():
            for field in ("name", "formula", "numerator", "denominator", "assumptions", "limitations"):
                self.assertTrue(d.get(field), f"{key}.{field} is empty")


class RealDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, _ = load_clean_dataset(BACKEND / "data" / "InsuranceData.csv")
        cls.report = A.build_analytics_report(cls.df)
        cls.m = cls.report["portfolio"]["metrics"]

    def test_known_portfolio_values(self):
        m = self.m
        self.assertEqual(m["policies"], 10000)
        self.assertEqual(m["claiming_policies"], 5646)
        self.assertAlmostEqual(m["claim_frequency"], 0.5646, places=4)
        self.assertAlmostEqual(m["claim_severity"], 2994.03, places=2)
        self.assertAlmostEqual(m["pure_premium"], 1690.43, places=2)
        self.assertAlmostEqual(m["average_premium"], 597.41, places=2)
        self.assertAlmostEqual(m["loss_ratio"], 2.8298, places=4)
        self.assertAlmostEqual(m["paid_loss_ratio"], 1.6916, places=4)
        self.assertLess(m["max_claim_to_coverage"], 1.0)

    def test_exposure_adjusted_frequency_close_to_incidence(self):
        self.assertAlmostEqual(self.m["claim_frequency_per_exposure_year"], self.m["claim_frequency"], delta=0.002)

    def test_all_segment_views_reconcile(self):
        for key in ("policy_type", "age_band", "gender"):
            segs = self.report[key]["segments"]
            self.assertEqual(sum(s["policies"] for s in segs), 10000, key)
            self.assertEqual(sum(s["claiming_policies"] for s in segs), 5646, key)
            self.assertAlmostEqual(sum(s["total_claim_amount"] for s in segs), self.m["total_claim_amount"], delta=0.05)

    def test_monthly_claims_sum_to_total(self):
        months = self.report["monthly"]["months"]
        self.assertEqual(sum(r["claims"] for r in months), 5646)
        self.assertAlmostEqual(sum(r["incurred_amount"] for r in months), self.m["total_claim_amount"], delta=0.05)
        self.assertTrue(any(r["low_exposure"] for r in months))      # first/last months are thin

    def test_exposure_adjustment_flattens_the_trend(self):
        rates = [r["claims_per_100_policy_months"] for r in self.report["monthly"]["months"] if not r["low_exposure"]]
        counts = [r["claims"] for r in self.report["monthly"]["months"] if not r["low_exposure"]]
        self.assertLess(pd.Series(rates).std() / pd.Series(rates).mean(), pd.Series(counts).std() / pd.Series(counts).mean())

    def test_status_view_matches_phase1_findings(self):
        rows = {r["status"]: r for r in self.report["claim_status"]["statuses"]}
        self.assertEqual(rows["Rejected"]["policies"], 4354)
        self.assertEqual(rows["Rejected"]["recorded_claim_amount"], 0.0)
        self.assertEqual((rows["Settled"]["policies"], rows["Pending"]["policies"]), (3386, 2260))

    def test_report_is_json_serialisable(self):
        json.dumps(self.report)

    def test_cleaned_csv_gives_same_answers(self):
        csv_path = BACKEND / "data" / "cleaned_insurance_data.csv"
        if not csv_path.exists():
            self.skipTest("run: python scripts/audit_dataset.py --save-clean")
        m2 = A.portfolio_summary(read_cleaned_csv(csv_path))["metrics"]
        for key in ("policies", "claiming_policies", "claim_frequency", "claim_severity", "pure_premium"):
            self.assertEqual(m2[key], self.m[key], key)
        self.assertAlmostEqual(m2["loss_ratio"], self.m["loss_ratio"], places=4)
        self.assertAlmostEqual(m2["total_earned_premium"], self.m["total_earned_premium"], delta=1.0)


if __name__ == "__main__":
    unittest.main()
