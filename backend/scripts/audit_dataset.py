"""
Dataset audit and cleaned-data export.

  python scripts/audit_dataset.py                 # print audit JSON
  python scripts/audit_dataset.py --save-clean    # also write data/cleaned_insurance_data.csv

The original CSV is only ever read, never modified.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import BACKEND_DIR, get_settings  # noqa: E402
from app.services.data_loader import load_clean_dataset  # noqa: E402
from app.services.data_quality import build_audit_report  # noqa: E402

CLEAN_PATH = BACKEND_DIR / "data" / "cleaned_insurance_data.csv"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=None)
    parser.add_argument("--save-clean", action="store_true")
    args = parser.parse_args()

    s = get_settings()
    df, cleaning = load_clean_dataset(args.path or s.data_path, s.valuation_date)
    print(json.dumps(build_audit_report(df, cleaning), indent=2))

    if args.save_clean:
        out = df.copy()
        out["AgeBand"] = out["AgeBand"].astype(str)
        out["EarnedFraction"] = out["EarnedFraction"].round(6)
        out["EarnedPremium"] = out["EarnedPremium"].round(2)
        out["ClaimToCoverage"] = out["ClaimToCoverage"].round(6)
        out.to_csv(CLEAN_PATH, index=False, date_format="%Y-%m-%d")
        print(f"\nSaved {len(out):,} rows x {out.shape[1]} columns -> {CLEAN_PATH}", file=sys.stderr)
