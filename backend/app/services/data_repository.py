"""
Data access with graceful fallback.

Order of preference:
  1. MongoDB   (only if MONGODB_URI is set and DATA_SOURCE != "csv")
  2. cleaned CSV  (backend/data/cleaned_insurance_data.csv)
  3. raw CSV, cleaned on the fly by data_loader

The API therefore keeps working when MongoDB is missing, misconfigured or down.
"""
from __future__ import annotations

import logging
import threading
from functools import lru_cache
from typing import Callable

import pandas as pd

from app.config import Settings, get_settings
from app.services import mongo_store
from app.services.data_loader import load_clean_dataset, normalize_cleaned_frame, read_cleaned_csv

logger = logging.getLogger(__name__)


class DataUnavailableError(RuntimeError):
    """No usable data source could be loaded."""


class DataRepository:
    def __init__(self, settings: Settings, mongo_loader: Callable[[Settings], pd.DataFrame] | None = None):
        self.settings = settings
        self._mongo_loader = mongo_loader or self._default_mongo_loader
        self._df: pd.DataFrame | None = None
        self._lock = threading.Lock()
        self.source: str | None = None
        self.mongodb_error: str | None = None

    @staticmethod
    def _default_mongo_loader(s: Settings) -> pd.DataFrame:
        return mongo_store.load_policies(s.mongodb_uri, s.mongodb_db, s.mongodb_collection)

    def load(self, force: bool = False) -> pd.DataFrame:
        with self._lock:
            if self._df is not None and not force:
                return self._df
            s = self.settings
            self.mongodb_error = None
            df, source = None, None

            if s.mongodb_uri and s.data_source != "csv":
                try:
                    df, source = self._mongo_loader(s), "mongodb"
                except Exception as exc:
                    self.mongodb_error = type(exc).__name__ + (f": {exc}" if isinstance(exc, mongo_store.MongoUnavailableError) else "")
                    logger.warning("MongoDB unavailable (%s) - falling back to CSV", type(exc).__name__)

            if df is None and s.cleaned_data_path.exists():
                try:
                    df, source = read_cleaned_csv(s.cleaned_data_path, s.valuation_date), "cleaned_csv"
                except Exception as exc:
                    logger.warning("Cleaned CSV unusable (%s) - trying raw CSV", type(exc).__name__)

            if df is None and s.data_path.exists():
                df, _ = load_clean_dataset(s.data_path, s.valuation_date)
                source = "raw_csv_pipeline"

            if df is None:
                raise DataUnavailableError(
                    "No data source available. Place InsuranceData.csv in backend/data/ "
                    "or run scripts/audit_dataset.py --save-clean.")

            df = normalize_cleaned_frame(df, s.valuation_date)
            if "valuation_date" not in df.attrs:
                if s.valuation_date:
                    df.attrs["valuation_date"] = s.valuation_date
                elif df["ClaimDate"].notna().any():
                    df.attrs["valuation_date"] = df["ClaimDate"].max().strftime("%Y-%m-%d")
            self._df, self.source = df, source
            logger.info("Loaded %d policies from %s", len(df), source)
            return df

    @property
    def df(self) -> pd.DataFrame:
        return self._df if self._df is not None else self.load()

    def status(self) -> dict:
        """Non-throwing summary for the health endpoint."""
        try:
            df = self.load()
            loaded, error = True, None
        except Exception as exc:
            df, loaded, error = None, False, str(exc)
        return {
            "data_loaded": loaded,
            "data_source": self.source,
            "rows": None if df is None else int(len(df)),
            "valuation_date": None if df is None else df.attrs.get("valuation_date"),
            "mongodb_configured": bool(self.settings.mongodb_uri) and self.settings.data_source != "csv",
            "mongodb_error": self.mongodb_error,
            "error": error,
        }


@lru_cache
def get_repository() -> DataRepository:
    return DataRepository(get_settings())
