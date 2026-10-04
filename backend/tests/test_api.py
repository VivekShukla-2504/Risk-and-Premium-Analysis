"""
HTTP-level tests (routing, validation, CORS, headers). Skipped automatically if FastAPI is not installed.
Needs: pip install fastapi httpx
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.services.data_repository import DataRepository, get_repository
    from app.main import app
    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False


@unittest.skipUnless(HAVE_FASTAPI, "fastapi/httpx not installed")
class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.json()["data_source"], {"mongodb", "cleaned_csv", "raw_csv_pipeline"})

    def test_every_documented_endpoint_returns_meta_and_data(self):
        for path in ("/api/dashboard/summary", "/api/analytics/policy-types", "/api/analytics/age-bands",
                     "/api/analytics/claims", "/api/analytics/loss-ratio", "/api/analytics/severity",
                     "/api/analytics/frequency", "/api/analytics/monthly-trends", "/api/analytics/risk-segments",
                     "/api/analytics/rate-indication"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertEqual(set(r.json()), {"meta", "data"}, path)

    def test_filters_and_validation(self):
        r = self.client.get("/api/analytics/policy-types", params={"policy_type": "auto", "gender": "Female"})
        self.assertEqual(r.json()["meta"]["filters_applied"], {"policy_type": "Auto", "gender": "Female"})
        self.assertEqual(self.client.get("/api/analytics/policy-types", params={"policy_type": "Boat"}).status_code, 422)
        self.assertEqual(self.client.get("/api/analytics/policy-types", params={"age_band": "0-5"}).status_code, 422)
        self.assertEqual(self.client.get("/api/analytics/policy-types", params={"start_date": "not-a-date"}).status_code, 422)
        self.assertEqual(self.client.get("/api/analytics/policy-types",
                                         params={"start_date": "2025-01-02", "end_date": "2025-01-01"}).status_code, 422)

    def test_outcome_filter_flags_rate_metrics(self):
        meta = self.client.get("/api/dashboard/summary", params={"claim_status": "Settled"}).json()["meta"]
        self.assertFalse(meta["rate_metrics_valid"])

    def test_scenario_validation(self):
        ok = self.client.post("/api/analytics/scenario", json={"frequency_change_pct": 10})
        self.assertEqual(ok.status_code, 200)
        self.assertIn("not a prediction", ok.json()["data"]["disclaimer"])
        self.assertEqual(self.client.post("/api/analytics/scenario", json={"frequency_change_pct": 50}).status_code, 422)
        self.assertEqual(self.client.post("/api/analytics/scenario", json={"unknown_field": 1}).status_code, 422)

    def test_scenarios_reject_outcome_selected_scopes(self):
        for filters in ({"claim_status": "Settled"}, {"date_basis": "claim_date", "start_date": "2024-01-01"}):
            response = self.client.post("/api/analytics/scenario/compare", json={"filters": filters})
            self.assertEqual(response.status_code, 422)
            self.assertIn("claim outcome", response.json()["detail"])

    def test_scenario_compare(self):
        r = self.client.post("/api/analytics/scenario/compare", json={"frequency_change_pct": 5})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([s["key"] for s in r.json()["data"]["scenarios"]], ["baseline", "optimistic", "stress", "custom"])
        self.assertEqual(self.client.post("/api/analytics/scenario/compare", json={"severity_change_pct": -50}).status_code, 422)

    def test_rate_indication_validates_scope_and_target(self):
        response = self.client.get("/api/analytics/rate-indication", params={"policy_type": "Auto", "target_loss_ratio_pct": 70})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["meta"]["rate_metrics_valid"])
        self.assertEqual(payload["meta"]["filters_applied"], {"policy_type": "Auto"})
        self.assertEqual(payload["data"]["assumptions"]["target_loss_ratio_pct"], 70)
        self.assertTrue(payload["data"]["overall"]["indication_available"])
        self.assertIsNone(payload["data"]["overall"]["credibility_factor"])
        self.assertEqual(len(payload["data"]["by_policy_type"]), 1)

        self.assertEqual(
            self.client.get("/api/analytics/rate-indication", params={"target_loss_ratio_pct": 30}).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/analytics/rate-indication", params={"target_loss_ratio_pct": 100}).status_code,
            200,
        )
        for target in (29.99, 100.01):
            self.assertEqual(
                self.client.get("/api/analytics/rate-indication", params={"target_loss_ratio_pct": target}).status_code,
                422,
            )
        for filters in (
            {"claim_status": "Settled"},
            {"date_basis": "claim_date", "start_date": "2024-01-01"},
        ):
            rejected = self.client.get("/api/analytics/rate-indication", params=filters)
            self.assertEqual(rejected.status_code, 422)
            self.assertIn("claim outcome", rejected.json()["detail"])

        empty = self.client.get(
            "/api/analytics/rate-indication",
            params={"start_date": "2030-01-01", "end_date": "2030-12-31"},
        )
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["meta"]["policies_in_scope"], 0)
        self.assertIsNone(empty.json()["data"]["overall"])
        self.assertFalse(empty.json()["data"]["available"])

    def test_export_headers(self):
        r = self.client.get("/api/analytics/export", params={"section": "policy-types", "format": "csv"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["content-disposition"])
        self.assertTrue(r.headers["content-type"].startswith("text/csv"))
        self.assertEqual(self.client.get("/api/analytics/export", params={"section": "full", "format": "csv"}).status_code, 422)

    def test_rate_indication_csv_and_json_exports(self):
        csv_response = self.client.get("/api/analytics/export", params={
            "section": "rate-indication", "format": "csv", "target_loss_ratio_pct": 70,
        })
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("indicated_rate_change_pct", csv_response.text.splitlines()[0])
        self.assertIn("target_loss_ratio_pct", csv_response.text.splitlines()[0])
        self.assertIn(",70.0,", csv_response.text.splitlines()[1])
        self.assertIn("attachment; filename=\"insurance_rate_indication_", csv_response.headers["content-disposition"])

        json_response = self.client.get("/api/analytics/export", params={
            "section": "rate-indication", "format": "json", "target_loss_ratio_pct": 60,
        })
        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(json_response.json()["data"]["assumptions"]["target_loss_ratio_pct"], 60)
        self.assertEqual(json_response.json()["section"], "rate-indication")

        invalid_scope = self.client.get("/api/analytics/export", params={
            "section": "rate-indication", "claim_status": "Settled",
        })
        self.assertEqual(invalid_scope.status_code, 422)

    def test_cors_preflight_for_react_dev_server(self):
        r = self.client.options("/api/dashboard/summary", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5173")

    def test_methodology_and_docs(self):
        m = self.client.get("/api/methodology").json()
        self.assertIn("loss_ratio", m["metric_definitions"])
        self.assertIn("indicated_rate_change_pct", m["rate_indication"]["formulas"])
        self.assertTrue(any("filtered-portfolio row is the unblended reference" in x for x in m["rate_indication"]["assumptions"]))
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)

    def test_configured_valuation_date_flows_through_api_metrics_for_multiple_dates(self):
        backend = Path(__file__).resolve().parents[1]
        cleaned_path = backend / "data" / "cleaned_insurance_data.csv"
        raw_path = backend / "data" / "InsuranceData.csv"
        results = []
        try:
            for valuation_date in ("2024-06-30", "2024-12-31"):
                settings = Settings(
                    data_path=raw_path,
                    cleaned_data_path=cleaned_path,
                    data_source="csv",
                    cors_origins=[],
                    valuation_date=valuation_date,
                    mongodb_uri=None,
                    mongodb_db="test",
                    mongodb_collection="test",
                )
                repo = DataRepository(settings)
                def use_test_repository():
                    return repo

                app.dependency_overrides[get_repository] = use_test_repository
                summary_response = self.client.get("/api/dashboard/summary")
                claims_response = self.client.get("/api/analytics/claims")
                indication_response = self.client.get("/api/analytics/rate-indication")
                self.assertEqual(summary_response.status_code, 200)
                self.assertEqual(claims_response.status_code, 200)
                self.assertEqual(indication_response.status_code, 200)
                summary, claims, indication = (
                    summary_response.json(), claims_response.json(), indication_response.json()
                )
                self.assertEqual(summary["meta"]["valuation_date"], valuation_date)
                self.assertEqual(summary["data"]["basis"]["valuation_date"], valuation_date)
                self.assertEqual(indication["meta"]["valuation_date"], valuation_date)
                results.append((summary, claims, indication))
        finally:
            app.dependency_overrides.pop(get_repository, None)

        early, late = results
        kpis_early = {k["key"]: k["value"] for k in early[0]["data"]["kpis"]}
        kpis_late = {k["key"]: k["value"] for k in late[0]["data"]["kpis"]}
        self.assertLess(early[0]["meta"]["claims_in_scope"], late[0]["meta"]["claims_in_scope"])
        self.assertLess(kpis_early["claim_frequency"], kpis_late["claim_frequency"])
        self.assertLess(early[0]["data"]["secondary_metrics"]["total_earned_premium"],
                        late[0]["data"]["secondary_metrics"]["total_earned_premium"])
        for summary, claims, indication in results:
            kpis = {k["key"]: k["value"] for k in summary["data"]["kpis"]}
            earned = summary["data"]["secondary_metrics"]["total_earned_premium"]
            self.assertAlmostEqual(kpis["loss_ratio"], kpis["total_claim_amount"] / earned, places=6)
            self.assertEqual(kpis["total_claims"], summary["meta"]["claims_in_scope"])
            self.assertEqual(claims["meta"]["claims_in_scope"],
                             sum(row["claim_records"] for row in claims["data"]["claim_status"]["statuses"]))
            self.assertEqual(indication["data"]["overall"]["claiming_policies"], summary["meta"]["claims_in_scope"])
            self.assertAlmostEqual(indication["data"]["overall"]["incurred_claims"], kpis["total_claim_amount"], places=2)
            self.assertAlmostEqual(indication["data"]["overall"]["earned_premium"], earned, places=2)
        self.assertNotEqual(kpis_early["loss_ratio"], kpis_late["loss_ratio"])


if __name__ == "__main__":
    unittest.main()
