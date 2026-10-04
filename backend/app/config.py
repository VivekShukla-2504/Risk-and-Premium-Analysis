"""Central configuration. All secrets come from environment variables (.env, never committed)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:  # python-dotenv is optional at runtime; .env is only a convenience for local dev
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    data_path: Path          # raw CSV (fallback of last resort; cleaned on the fly)
    cleaned_data_path: Path  # preferred file source
    data_source: str         # "auto" (MongoDB if configured, else CSV) or "csv" (never touch MongoDB)
    cors_origins: list[str]
    # Optional "as-of" date used for the earned-premium proxy (YYYY-MM-DD).
    # If None, the latest ClaimDate in the data is used (see DATA_AUDIT.md).
    valuation_date: str | None
    # Optional MongoDB source. Credentials only ever live in environment variables.
    mongodb_uri: str | None
    mongodb_db: str
    mongodb_collection: str


@lru_cache
def get_settings() -> Settings:
    data_path = Path(os.getenv("DATA_PATH", BACKEND_DIR / "data" / "InsuranceData.csv"))
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    source = os.getenv("DATA_SOURCE", "auto").strip().lower()
    if source not in {"auto", "csv"}:
        raise ValueError("DATA_SOURCE must be 'auto' or 'csv'")
    return Settings(
        data_path=data_path,
        cleaned_data_path=Path(os.getenv("CLEANED_DATA_PATH", BACKEND_DIR / "data" / "cleaned_insurance_data.csv")),
        data_source=source,
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        valuation_date=os.getenv("VALUATION_DATE") or None,
        mongodb_uri=os.getenv("MONGODB_URI") or None,
        mongodb_db=os.getenv("MONGODB_DB", "insurance_analytics"),
        mongodb_collection=os.getenv("MONGODB_COLLECTION", "policies"),
    )
