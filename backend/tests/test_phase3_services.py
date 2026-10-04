"""Tests for statistics, filters, repository fallback, scenarios, risk segments and report builders."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.services import filters as F  # noqa: E402
from app.services import report_service as RS  # noqa: E402
from app.services import risk_segmentation as R  # noqa: E402
from app.services import scenario_service as S  # noqa: E402
from app.services import statistics as ST  # noqa: E402
from app.services.data_loader import clean_data, load_clean_dataset, read_cleaned_csv  # noqa: E402
from app.services.data_repository import DataRepository, DataUnavailableError  # noqa: E402
from app.services.mongo_store import MongoUnavailableError  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
RAW = BACKEND / "data" / "InsuranceData.csv"
CLEANED = BACKEND / "data" / "cleaned_insurance_data.csv"
COLS = ["PolicyNumber", "CustomerID", "Gender", "Age", "PolicyType", "PolicyStartDate", "PolicyEndDate",
        "PremiumAmount", "CoverageAmount", "ClaimNumber", "ClaimDate", "ClaimAmount", "ClaimStatus"]


def row(n, gender, age, ptype, prem, cov, status, amount, claim_date, start="01-01-2024"):
    return [f"P{n}", f"C{n}", gender, str(age), ptype, start, "01-01-2025", str(prem), str(cov), f"C{n}",
            claim_date, str(amount), status]


# Same hand-checked portfolio as test_analytics_service (premium 3500, incurred 5000, 4 claims / 6 policies)
HAND = [
    row(1, "Male", 20, "Auto", 1000, 50000, "Settled", 2000, "15-03-2024"),
    row(2, "Female", 30, "Auto", 800, 40000, "Pending", 1000, "20-03-2024"),
    row(3, "Male", 40, "Auto", 600, 30000, "Rejected", 0, None),
    row(4, "Female", 50, "Home", 500, 20000, "Rejected", 0, None),
    row(5, "Male", 60, "Home", 400, 10000, "Settled", 500, "10-05-2024"),
    row(6, "Female", 70, "Travel", 200, 10000, "Settled", 1500, "05-05-2024"),
]


def hand_df():
    df, _ = clean_data(pd.DataFrame(HAND, columns=COLS).astype("string"), valuation_date="2025-01-01")
    return df


class DistributionFunctions(unittest.TestCase):
    """Reference values computed with SciPy."""

    def test_chi_square_survival(self):
        self.assertAlmostEqual(ST.chi2_sf(7.5, 4), 0.11170929281604328, places=10)
        self.assertAlmostEqual(ST.chi2_sf(0.3, 1), 0.583882420770365, places=10)
        self.assertAlmostEqual(ST.chi2_sf(25, 6), 0.00034145459689170836, places=12)
        self.assertEqual(ST.chi2_sf(0, 3), 1.0)

    def test_f_survival(self):
        self.assertAlmostEqual(ST.f_sf(2.5, 4, 100), 0.047239238913594384, places=10)
        self.assertAlmostEqual(ST.f_sf(0.5, 1, 5000), 0.4795330752748634, places=10)
        self.assertAlmostEqual(ST.f_sf(10, 3, 20), 0.0003094054635144071, places=12)

    def test_matches_scipy_when_available(self):
        try:
            from scipy.stats import chi2, f
        except ImportError:
            self.skipTest("scipy not installed")
        for x, d in [(1.2, 2), (9.9, 5), (40, 9), (0.05, 1)]:
            self.assertAlmostEqual(ST.chi2_sf(x, d), chi2.sf(x, d), places=10)
        for x, a, b in [(1.7, 2, 50), (0.3, 6, 400), (6.0, 4, 9)]:
            self.assertAlmostEqual(ST.f_sf(x, a, b), f.sf(x, a, b), places=10)

    def test_chi_square_homogeneity_identical_rates_gives_zero(self):
        r = ST.chi_square_homogeneity([50, 100], [100, 200])
        self.assertAlmostEqual(r["statistic"], 0.0, places=8)
        self.assertEqual(r["p_value"], 1.0)
        self.assertFalse(r["significant_at_5pct"])

    def test_chi_square_homogeneity_detects_real_difference(self):
        r = ST.chi_square_homogeneity([90, 10], [100, 100])
        self.assertTrue(r["significant_at_5pct"])
        self.assertLess(r["p_value"], 1e-6)

    def test_chi_square_not_computable_cases(self):
        self.assertFalse(ST.chi_square_homogeneity([5], [10])["computable"])
        self.assertFalse(ST.chi_square_homogeneity([0, 0], [10, 10])["computable"])
        self.assertFalse(ST.chi_square_homogeneity([10, 10], [10, 10])["computable"])

    def test_anova(self):
        r = ST.one_way_anova([np.array([1.0, 2, 3]), np.array([2.0, 3, 4]), np.array([5.0, 6, 7])])
        self.assertAlmostEqual(r["statistic"], 13.0, places=3)     # means 2,3,6: SSB=26, SSW=6 -> (26/2)/(6/6) = 13
        self.assertTrue(r["significant_at_5pct"])
        self.assertFalse(ST.one_way_anova([np.array([1.0, 2.0])])["computable"])

    def test_z_test(self):
        r = ST.z_test_vs_expected(60, 100, 0.5)
        self.assertAlmostEqual(r["z_score"], 2.0, places=4)
        self.assertAlmostEqual(r["p_value"], 0.0455, places=3)
        self.assertTrue(r["significant_at_5pct"])
        self.assertIsNone(ST.z_test_vs_expected(5, 0, 0.5)["z_score"])


class Filters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = hand_df()

    def run_filter(self, **kw):
        spec = F.resolve_filters(self.df, F.FilterSpec(**kw))
        return F.apply_filters(self.df, spec)

    def test_policy_type_and_case_insensitive(self):
        out, warn, valid = self.run_filter(policy_type="auto")
        self.assertEqual(len(out), 3)
        self.assertTrue(valid)

    def test_combined_filters(self):
        out, _, _ = self.run_filter(policy_type="Auto", gender="Male")
        self.assertEqual(sorted(out["PolicyNumber"]), ["P1", "P3"])

    def test_age_band(self):
        out, _, _ = self.run_filter(age_band="46-55")
        self.assertEqual(out["PolicyNumber"].tolist(), ["P4"])

    def test_invalid_values_rejected_with_allowed_list(self):
        with self.assertRaises(F.FilterValidationError) as cm:
            self.run_filter(policy_type="Boat")
        self.assertIn("Auto", str(cm.exception))
        with self.assertRaises(F.FilterValidationError):
            self.run_filter(age_band="0-5")
        with self.assertRaises(F.FilterValidationError):
            self.run_filter(date_basis="nonsense")
        with self.assertRaises(F.FilterValidationError):
            self.run_filter(start_date=dt.date(2025, 1, 2), end_date=dt.date(2025, 1, 1))

    def test_claim_status_invalidates_rate_metrics(self):
        out, warn, valid = self.run_filter(claim_status="Settled")
        self.assertEqual(len(out), 3)
        self.assertFalse(valid)
        self.assertTrue(any("claim_status" in w for w in warn))

    def test_policy_start_date_keeps_whole_cohort(self):
        out, _, valid = self.run_filter(start_date=dt.date(2024, 1, 1), end_date=dt.date(2024, 12, 31))
        self.assertEqual(len(out), 6)           # no-claim policies kept
        self.assertTrue(valid)

    def test_claim_date_basis_drops_no_claim_policies_and_warns(self):
        out, warn, valid = self.run_filter(start_date=dt.date(2024, 3, 1), end_date=dt.date(2024, 3, 31), date_basis="claim_date")
        self.assertEqual(sorted(out["PolicyNumber"]), ["P1", "P2"])
        self.assertFalse(valid)

    def test_empty_result_warns_and_does_not_crash(self):
        out, warn, _ = self.run_filter(policy_type="Travel", gender="Male")
        self.assertEqual(len(out), 0)
        self.assertTrue(any("No policies" in w for w in warn))
        self.assertIsNotNone(RS.policy_types_report(out))     # builders cope with empty scope

    def test_applied_summary_and_options(self):
        spec = F.resolve_filters(self.df, F.FilterSpec(policy_type="auto", start_date=dt.date(2024, 1, 1)))
        self.assertEqual(spec.applied(), {"policy_type": "Auto", "start_date": "2024-01-01", "date_basis": "policy_start"})
        opts = F.filter_options(self.df)
        self.assertEqual(opts["policy_type"], ["Auto", "Home", "Travel"])
        self.assertEqual(opts["claim_status"], ["Settled", "Pending", "Rejected"])


class RepositoryFallback(unittest.TestCase):
    def settings(self, tmp, uri="mongodb://user:secret@host/db", source="auto", cleaned=True, raw=True):
        return Settings(
            data_path=RAW if raw else Path(tmp) / "missing_raw.csv",
            cleaned_data_path=CLEANED if cleaned else Path(tmp) / "missing_cleaned.csv",
            data_source=source, cors_origins=[], valuation_date=None,
            mongodb_uri=uri, mongodb_db="d", mongodb_collection="c")

    def test_falls_back_to_cleaned_csv_when_mongo_down(self):
        def boom(_s):
            raise MongoUnavailableError("ServerSelectionTimeoutError while reading MongoDB")
        with tempfile.TemporaryDirectory() as tmp:
            repo = DataRepository(self.settings(tmp), mongo_loader=boom)
            self.assertEqual(len(repo.load()), 10000)
            self.assertEqual(repo.source, "cleaned_csv")
            st = repo.status()
            self.assertTrue(st["data_loaded"])
            self.assertIn("ServerSelectionTimeoutError", st["mongodb_error"])
            self.assertNotIn("secret", json.dumps(st))          # credentials never surface
            self.assertEqual(st["valuation_date"], "2025-07-08")

    def test_unexpected_mongo_exception_also_falls_back_without_leaking_message(self):
        def boom(_s):
            raise RuntimeError("connection to mongodb://user:secret@host failed")
        with tempfile.TemporaryDirectory() as tmp:
            repo = DataRepository(self.settings(tmp), mongo_loader=boom)
            repo.load()
            self.assertEqual(repo.source, "cleaned_csv")
            self.assertNotIn("secret", repo.mongodb_error)

    def test_uses_mongo_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DataRepository(self.settings(tmp), mongo_loader=lambda _s: read_cleaned_csv(CLEANED).head(50))
            self.assertEqual(len(repo.load()), 50)
            self.assertEqual(repo.source, "mongodb")

    def test_csv_mode_never_calls_mongo(self):
        def must_not_call(_s):
            raise AssertionError("mongo loader called")
        with tempfile.TemporaryDirectory() as tmp:
            repo = DataRepository(self.settings(tmp, source="csv"), mongo_loader=must_not_call)
            repo.load()
            self.assertEqual(repo.source, "cleaned_csv")

    def test_no_uri_means_no_mongo_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DataRepository(self.settings(tmp, uri=None), mongo_loader=lambda _s: 1 / 0)
            repo.load()
            self.assertIsNone(repo.mongodb_error)

    def test_raw_pipeline_when_cleaned_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DataRepository(self.settings(tmp, uri=None, cleaned=False))
            self.assertEqual(len(repo.load()), 10000)
            self.assertEqual(repo.source, "raw_csv_pipeline")

    def test_nothing_available_raises_and_status_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DataRepository(self.settings(tmp, uri=None, cleaned=False, raw=False))
            with self.assertRaises(DataUnavailableError):
                repo.load()
            st = repo.status()
            self.assertFalse(st["data_loaded"])
            self.assertIn("No data source", st["error"])


class Scenario(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = hand_df()

    def test_zero_shock_reproduces_baseline(self):
        r = S.compute_scenario(self.df, S.ScenarioInputs())
        self.assertAlmostEqual(r["base"]["loss_ratio"], 5000 / 3500, places=6)
        self.assertEqual(r["base"], r["scenario"])
        self.assertEqual(r["change"]["loss_ratio"]["absolute"], 0)

    def test_hand_calculation(self):
        inp = S.ScenarioInputs(frequency_change_pct=10, severity_change_pct=-5, inflation_pct=3,
                               premium_adjustment_pct=5, expense_ratio_pct=25)
        r = S.compute_scenario(self.df, inp)
        cost = 5000 * 1.10 * 0.95 * 1.03                     # policies x f x s with multiplicative shocks
        premium = 3500 * 1.05
        self.assertAlmostEqual(r["scenario"]["expected_claim_cost"], cost, places=1)
        self.assertAlmostEqual(r["scenario"]["earned_premium"], premium, places=1)
        self.assertAlmostEqual(r["scenario"]["loss_ratio"], cost / premium, places=5)
        self.assertAlmostEqual(r["scenario"]["claim_frequency"], (4 / 6) * 1.1, places=5)
        self.assertAlmostEqual(r["scenario"]["claim_severity"], 1250 * 0.95 * 1.03, delta=0.01)   # stored to 2 dp
        self.assertAlmostEqual(r["profitability_indicator"]["scenario_margin"], 1 - cost / premium - 0.25, places=5)
        self.assertAlmostEqual(r["profitability_indicator"]["scenario_result"], premium - cost - 0.25 * premium, places=1)
        self.assertFalse(r["profitability_indicator"]["scenario_is_profitable"])

    def test_premium_needed(self):
        r = S.compute_scenario(self.df, S.ScenarioInputs(expense_ratio_pct=20, target_loss_ratio_pct=50))
        self.assertAlmostEqual(r["premium_needed"]["for_target_loss_ratio"]["required_earned_premium"], 5000 / 0.5, places=1)
        self.assertAlmostEqual(r["premium_needed"]["to_break_even"]["required_earned_premium"], 5000 / 0.8, places=1)

    def test_grid_centre_equals_scenario_with_no_freq_sev_shock(self):
        r = S.compute_scenario(self.df, S.ScenarioInputs(inflation_pct=4, premium_adjustment_pct=2))
        g = r["sensitivity_grid"]
        centre = g["loss_ratio"][g["severity_changes_pct"].index(0.0)][g["frequency_changes_pct"].index(0.0)]
        self.assertAlmostEqual(centre, r["scenario"]["loss_ratio"], places=6)
        # raising frequency raises loss ratio (monotonic along a row)
        row_ = g["loss_ratio"][2]
        self.assertEqual(row_, sorted(row_))

    def test_assumption_effects_are_unranked_and_premium_effect_is_negative(self):
        r = S.compute_scenario(self.df, S.ScenarioInputs())
        effects = r["one_at_a_time_sensitivity"]
        self.assertEqual([t["driver"] for t in effects],
                         ["Claim frequency", "Claim severity", "Claim-cost inflation", "Premium"])
        self.assertIn("Shocks are not estimated from experience", r["sensitivity_comparison_note"])
        prem = next(t for t in r["one_at_a_time_sensitivity"] if t["driver"] == "Premium")
        self.assertGreater(prem["loss_ratio_at_minus"], prem["loss_ratio_at_plus"])   # more premium -> lower LR

    def test_by_policy_type(self):
        r = S.compute_scenario(self.df, S.ScenarioInputs(frequency_change_pct=20))
        auto = next(x for x in r["by_policy_type"] if x["policy_type"] == "Auto")
        self.assertAlmostEqual(auto["base_loss_ratio"], 3000 / 2400, places=6)
        self.assertAlmostEqual(auto["scenario_loss_ratio"], 3000 * 1.2 / 2400, places=6)

    def test_validation_limits(self):
        for kw in ({"frequency_change_pct": 25}, {"severity_change_pct": -21}, {"inflation_pct": 31},
                   {"premium_adjustment_pct": -31}, {"expense_ratio_pct": 61}, {"target_loss_ratio_pct": 10}):
            with self.assertRaises(S.ScenarioError, msg=str(kw)):
                S.compute_scenario(self.df, S.ScenarioInputs(**kw))
        S.compute_scenario(self.df, S.ScenarioInputs(frequency_change_pct=-20, severity_change_pct=20))  # boundary ok

    def test_no_claims_or_empty_scope_is_an_error_not_a_crash(self):
        with self.assertRaises(S.ScenarioError):
            S.compute_scenario(self.df.iloc[0:0], S.ScenarioInputs())
        with self.assertRaises(S.ScenarioError):
            S.compute_scenario(self.df[self.df["ClaimStatus"] == "Rejected"], S.ScenarioInputs())

    def test_output_contains_disclaimer_and_is_json_safe(self):
        r = S.compute_scenario(self.df, S.ScenarioInputs(5, 5, 2, 1))
        self.assertIn("not a prediction", r["disclaimer"])
        json.dumps(r, allow_nan=False)


class RiskSegments(unittest.TestCase):
    def test_tier_points_on_hand_data(self):
        df = hand_df().assign(CoverageAmount=lambda d: d["CoverageAmount"])
        # P1: age 20 Auto (+1), cov 50000 -> 1 point -> Medium ; P4: Home age 50, cov 20000 -> Low
        tiers = R.assign_apriori_tier(df)
        self.assertEqual(tiers.iloc[0], "Medium")
        self.assertEqual(tiers.iloc[3], "Low")

    def test_home_is_exempt_from_age_points_and_high_requires_both(self):
        df = hand_df().iloc[[3]].assign(Age=80, CoverageAmount=90000)      # Home, old, high cover
        self.assertEqual(R.assign_apriori_tier(df).iloc[0], "Medium")      # only coverage point
        df2 = hand_df().iloc[[0]].assign(Age=80, CoverageAmount=90000)     # Auto, old, high cover
        self.assertEqual(R.assign_apriori_tier(df2).iloc[0], "High")

    def test_claim_classes(self):
        df = hand_df()
        classes = R.assign_claim_class(df)
        self.assertEqual(classes.iloc[2], "No payable claim")                # P3 rejected
        self.assertEqual(classes.iloc[0], "Claim 2-5% of cover")             # P1: 2000/50000 = 4%
        self.assertEqual(classes.iloc[5], "Claim >=10% of cover")            # P6: 1500/10000 = 15%

    def test_real_data_conclusion_and_reconciliation(self):
        df, _ = load_clean_dataset(RAW)
        res = R.risk_segments(df)
        self.assertEqual(sum(t["policies"] for t in res["a_priori_tiers"]), 10000)
        self.assertEqual(sum(c["policies"] for c in res["claim_experience_classes"]), 10000)
        self.assertEqual([t["segment"] for t in res["a_priori_tiers"]], ["Low", "Medium", "High"])
        self.assertAlmostEqual(res["portfolio_claim_frequency"], 0.5646, places=4)
        self.assertFalse(res["tiers_supported_by_experience"])
        self.assertIn("does NOT", res["conclusion"])
        self.assertAlmostEqual(sum(a["actual_claims"] for a in res["actual_vs_expected"]), 5646)
        self.assertAlmostEqual(sum(a["expected_claims"] for a in res["actual_vs_expected"]), 5646, delta=0.1)


class ReportBuilders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, _ = load_clean_dataset(RAW)
        cls.opts = F.filter_options(cls.df)

    def test_dashboard_kpis(self):
        kpis = {k["key"]: k for k in RS.dashboard_summary(self.df, self.opts)["kpis"]}
        self.assertEqual(list(kpis), ["total_policies", "total_premium", "total_coverage", "total_claims",
                                      "total_claim_amount", "loss_ratio", "average_claim_severity", "claim_frequency"])
        self.assertEqual(kpis["total_policies"]["value"], 10000)
        self.assertEqual(kpis["total_claims"]["value"], 5646)
        self.assertAlmostEqual(kpis["loss_ratio"]["value"], 2.8298, places=4)
        self.assertEqual(kpis["loss_ratio"]["format"], "percent")
        self.assertEqual({k for k, v in kpis.items() if v["rate_metric"]}, {"loss_ratio", "claim_frequency"})

    def test_every_builder_is_strict_json_safe_for_full_and_filtered_scopes(self):
        auto = self.df[self.df["PolicyType"] == "Auto"]
        empty = self.df.iloc[0:0]
        for scope in (self.df, auto, empty):
            for fn in (RS.policy_types_report, RS.age_bands_report, RS.claims_report, RS.loss_ratio_report,
                       RS.severity_report, RS.frequency_report, RS.monthly_trends_report, RS.risk_segments_report):
                json.dumps(fn(scope), allow_nan=False)
            json.dumps(RS.dashboard_summary(scope, self.opts), allow_nan=False)

    def test_policy_type_report_matches_analytics_and_has_tests(self):
        rep = RS.policy_types_report(self.df)
        self.assertEqual(sum(s["policies"] for s in rep["segments"]), 10000)
        self.assertAlmostEqual(rep["statistical_tests"]["claim_frequency"]["p_value"], 0.175127, places=4)
        self.assertFalse(rep["statistical_tests"]["claim_frequency"]["significant_at_5pct"])
        self.assertEqual(len(rep["actual_vs_expected"]), 5)

    def test_claims_report_coverage_bands_and_points(self):
        rep = RS.claims_report(self.df, include_points=True, max_points=100)
        bands = rep["coverage_bands"]["bands"]
        self.assertEqual(sum(b["policies"] for b in bands), 10000)
        self.assertEqual(len(rep["points"]["claims"]), 100)
        self.assertEqual(RS.claims_report(self.df, True, 100)["points"], rep["points"])      # deterministic sample
        self.assertFalse(rep["correlations"]["premium_vs_coverage"]["distinguishable_from_zero"])

    def test_loss_ratio_report_shows_written_basis_only_as_reference(self):
        rep = RS.loss_ratio_report(self.df)
        self.assertAlmostEqual(rep["portfolio"]["loss_ratio"], 2.8298, places=4)
        self.assertAlmostEqual(rep["portfolio"]["loss_ratio_on_written_premium"], 16904295.27 / 5974060.08, places=3)

    def test_severity_and_frequency_reports(self):
        sev = RS.severity_report(self.df)
        self.assertEqual(sev["overall"]["claims"], 5646)
        self.assertEqual(sum(h["claims"] for h in sev["histogram"]), 5646)
        self.assertLess(sev["overall"]["ci_95_low"], sev["overall"]["mean"])
        fr = RS.frequency_report(self.df)
        self.assertEqual(sum(s["claiming_policies"] for s in fr["by_gender"]["segments"]), 5646)

    def test_monthly_summary_shows_exposure_adjustment_reduces_variation(self):
        s = RS.monthly_trends_report(self.df)["summary"]
        self.assertLess(s["coefficient_of_variation_exposure_adjusted"], s["coefficient_of_variation_raw_counts"])

    def test_csv_export_and_formula_injection_guard(self):
        csv_text = RS.to_csv(RS.export_table(self.df, "policy-types"))
        self.assertTrue(csv_text.splitlines()[0].startswith("segment,policies"))
        self.assertEqual(len(csv_text.strip().splitlines()), 6)
        evil = pd.DataFrame({"name": ["=HYPERLINK(\"x\")", "+1", "ok"], "n": [-1, 2, 3]})
        out = RS.to_csv(evil).splitlines()
        self.assertTrue(out[1].startswith("\"'=") or out[1].startswith("'="))
        self.assertTrue(out[2].startswith("'+1"))
        self.assertTrue(out[3].startswith("ok"))
        self.assertIn("-1", out[1])            # numbers untouched

    def test_policy_level_export_shape(self):
        t = RS.export_table(self.df, "policies")
        self.assertEqual(t.shape[0], 10000)
        self.assertEqual(t["PolicyStartDate"].iloc[0][4], "-")                 # ISO date text
        with self.assertRaises(ValueError):
            RS.export_table(self.df, "full")

    def test_export_filename(self):
        self.assertEqual(RS.export_filename("policy-types", "csv", dt.date(2026, 10, 3)), "insurance_policy_types_20261003.csv")

    def test_meta_flags(self):
        spec = F.FilterSpec(policy_type="Auto")
        scoped = self.df[self.df["PolicyType"] == "Auto"]
        meta = RS.build_meta(source="cleaned_csv", spec=spec, full_df=self.df, scoped_df=scoped, warnings=[], rate_metrics_valid=True)
        self.assertEqual((meta["policies_total"], meta["policies_in_scope"]), (10000, 1594))
        self.assertEqual(meta["filters_applied"], {"policy_type": "Auto"})
        self.assertIn("SYNTHETIC", meta["disclaimer"])


if __name__ == "__main__":
    unittest.main()
