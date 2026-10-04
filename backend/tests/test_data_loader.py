"""Run with:  python -m unittest discover -s tests   (or pytest)"""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.data_loader import DataValidationError, clean_data, load_clean_dataset  # noqa: E402
from app.services.data_quality import build_audit_report  # noqa: E402
from app.config import Settings  # noqa: E402
from app.services.data_repository import DataRepository  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data" / "InsuranceData.csv"
COLS = ["PolicyNumber", "CustomerID", "Gender", "Age", "PolicyType", "PolicyStartDate", "PolicyEndDate",
        "PremiumAmount", "CoverageAmount", "ClaimNumber", "ClaimDate", "ClaimAmount", "ClaimStatus"]


def make(rows):
    return pd.DataFrame(rows, columns=COLS).astype("string")


ROW_OK = ["P1", "C1", "Male", "40", "Auto", "01-01-2024", "01-01-2025", "1000", "50000", "C1", "01-07-2024", "2000", "Settled"]
ROW_NOCLAIM = ["P2", "C2", "Female", "30", "Home", "01-01-2024", "01-01-2025", "500", "20000", "C2", None, "0", "Rejected"]
ROW_PENDING = ["P3", "C3", "Male", "70", "Travel", "01-01-2024", "01-01-2025", "400", "10000", "C3", "01-10-2024", "1000", "Pending"]


class SyntheticCases(unittest.TestCase):
    def test_exact_duplicates_removed(self):
        df, rep = clean_data(make([ROW_OK, ROW_OK, ROW_NOCLAIM]))
        self.assertEqual(len(df), 2)
        self.assertEqual(rep.exact_duplicate_rows_removed, 1)

    def test_dates_parsed_day_first(self):
        df, _ = clean_data(make([ROW_OK]))
        self.assertEqual(df.loc[0, "ClaimDate"], pd.Timestamp(2024, 7, 1))  # 01-07 = 1 July, not 7 Jan

    def test_missing_claim_date_kept_as_nat_and_zero_amount_is_no_claim(self):
        df, rep = clean_data(make([ROW_NOCLAIM]))
        self.assertTrue(pd.isna(df.loc[0, "ClaimDate"]))
        self.assertFalse(df.loc[0, "IsClaim"])
        self.assertEqual(rep.claim_dates_unparseable, 0)

    def test_status_treatment(self):
        df, _ = clean_data(make([ROW_OK, ROW_PENDING, ROW_NOCLAIM]))
        by = df.set_index("PolicyNumber")
        self.assertEqual(by.loc["P1", "PaidAmount"], 2000)
        self.assertEqual(by.loc["P3", "PaidAmount"], 0)
        self.assertEqual(by.loc["P3", "OutstandingAmount"], 1000)
        self.assertEqual(by.loc["P2", "IncurredAmount"], 0)

    def test_invalid_rows_dropped_and_counted(self):
        bad = list(ROW_OK); bad[0] = "P9"; bad[7] = "abc"           # non-numeric premium
        bad2 = list(ROW_OK); bad2[0] = "P8"; bad2[5] = "31-31-2024"  # impossible date
        df, rep = clean_data(make([ROW_OK, bad, bad2]))
        self.assertEqual(len(df), 1)
        self.assertEqual(rep.rows_dropped_invalid["missing_or_nonpositive_premium"], 1)
        self.assertEqual(rep.rows_dropped_invalid["invalid_policy_dates"], 1)

    def test_earned_premium_pro_rata(self):
        df, _ = clean_data(make([ROW_OK, ROW_PENDING]), valuation_date="2024-07-01")  # ~half a year
        frac = df.loc[0, "EarnedFraction"]
        self.assertAlmostEqual(frac, 182 / 366, places=4)
        self.assertAlmostEqual(df.loc[0, "EarnedPremium"], 1000 * 182 / 366, places=2)

    def test_claims_and_earned_premium_follow_each_valuation_date_on_raw_and_cleaned_data(self):
        raw = make([ROW_OK, ROW_PENDING])
        as_of_june, _ = clean_data(raw, valuation_date="2024-06-30")
        as_of_july, _ = clean_data(raw, valuation_date="2024-07-01")
        as_of_december, _ = clean_data(raw, valuation_date="2024-12-31")

        self.assertEqual(int(as_of_june["IsClaim"].sum()), 0)
        self.assertEqual(float(as_of_june["IncurredAmount"].sum()), 0)
        self.assertTrue(as_of_june["ClaimMonth"].isna().all())
        self.assertTrue((as_of_june["ClaimStatusAsOf"] == "Not yet occurred as of valuation date").all())
        self.assertEqual(int(as_of_july["IsClaim"].sum()), 1)
        self.assertEqual(as_of_july["ClaimStatusAsOf"].tolist(),
                         ["Settled", "Not yet occurred as of valuation date"])
        self.assertEqual(float(as_of_july["IncurredAmount"].sum()), 2000)
        self.assertEqual(int(as_of_december["IsClaim"].sum()), 2)
        self.assertEqual(float(as_of_december["IncurredAmount"].sum()), 3000)
        self.assertLess(as_of_june["EarnedPremium"].sum(), as_of_july["EarnedPremium"].sum())
        self.assertLess(as_of_july["EarnedPremium"].sum(), as_of_december["EarnedPremium"].sum())
        self.assertEqual(as_of_june.attrs["valuation_date"], "2024-06-30")
        self.assertEqual(as_of_december.attrs["valuation_date"], "2024-12-31")

        import tempfile
        from app.services.data_loader import read_cleaned_csv

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cleaned.csv"
            as_of_december.to_csv(path, index=False)
            cleaned_june = read_cleaned_csv(path, valuation_date="2024-06-30")
            cleaned_july = read_cleaned_csv(path, valuation_date="2024-07-01")
            self.assertEqual(cleaned_june.attrs["valuation_date"], "2024-06-30")
            self.assertEqual(int(cleaned_june["IsClaim"].sum()), 0)
            self.assertTrue((cleaned_june["ClaimStatusAsOf"] == "Not yet occurred as of valuation date").all())
            self.assertEqual(int(cleaned_july["IsClaim"].sum()), 1)
            self.assertAlmostEqual(cleaned_june["EarnedPremium"].sum(), as_of_june["EarnedPremium"].sum(), places=2)

    def test_valuation_date_requires_iso_calendar_date(self):
        with self.assertRaisesRegex(DataValidationError, "must be YYYY-MM-DD"):
            clean_data(make([ROW_OK]), valuation_date="12/31/2024")

    def test_missing_columns_raise(self):
        from app.services.data_loader import load_raw_csv
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("PolicyNumber,Age\nP1,3\n")
        try:
            with self.assertRaises(DataValidationError):
                load_raw_csv(f.name)
        finally:
            os.unlink(f.name)

    def test_repository_applies_valuation_date_to_cleaned_raw_and_mongo_sources(self):
        cleaned, _ = load_clean_dataset(DATA)

        def settings(cleaned_path, valuation_date="2024-12-31", data_source="csv", mongodb_uri=None):
            return Settings(
                data_path=DATA,
                cleaned_data_path=cleaned_path,
                data_source=data_source,
                cors_origins=[],
                valuation_date=valuation_date,
                mongodb_uri=mongodb_uri,
                mongodb_db="test",
                mongodb_collection="test",
            )

        for label, repo in (
            ("cleaned_csv", DataRepository(settings(DATA.parent / "cleaned_insurance_data.csv"))),
            ("raw_csv_pipeline", DataRepository(settings(Path("missing-cleaned.csv"), data_source="csv"))),
            ("mongodb", DataRepository(
                settings(Path("missing-cleaned.csv"), data_source="auto", mongodb_uri="mongodb://test"),
                mongo_loader=lambda _: cleaned.copy(),
            )),
        ):
            with self.subTest(source=label):
                result = repo.load()
                self.assertEqual(repo.source, label)
                self.assertEqual(result.attrs["valuation_date"], "2024-12-31")
                self.assertLess(int(result["IsClaim"].sum()), int(cleaned["IsClaim"].sum()))
                self.assertTrue((result.loc[result["ClaimDate"] > pd.Timestamp("2024-12-31"), "IncurredAmount"] == 0).all())
                self.assertTrue((result.loc[result["ClaimDate"] > pd.Timestamp("2024-12-31"), "EarnedPremium"]
                                 <= result.loc[result["ClaimDate"] > pd.Timestamp("2024-12-31"), "PremiumAmount"]).all())


class RealDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.rep = load_clean_dataset(DATA)

    def test_counts_match_manual_inspection(self):
        self.assertEqual(self.rep.rows_raw, 10004)
        self.assertEqual(self.rep.exact_duplicate_rows_removed, 4)
        self.assertEqual(len(self.df), 10000)
        self.assertTrue(self.df["PolicyNumber"].is_unique)

    def test_claim_structure(self):
        self.assertEqual(int(self.df["IsClaim"].sum()), 5646)
        self.assertEqual(int((self.df["ClaimStatus"] == "Rejected").sum()), 4354)

    def test_no_logical_inconsistencies(self):
        checks = build_audit_report(self.df, self.rep)["consistency_checks"]
        self.assertTrue(all(v == 0 for v in checks.values()), checks)

    def test_earned_never_exceeds_written(self):
        self.assertTrue((self.df["EarnedPremium"] <= self.df["PremiumAmount"] + 1e-9).all())

    def test_report_is_json_serialisable(self):
        import json
        json.dumps(build_audit_report(self.df, self.rep))


if __name__ == "__main__":
    unittest.main()
