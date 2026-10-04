"""
Optional MongoDB persistence for the cleaned policy data.

Kept deliberately separate: nothing else imports pymongo, and the import happens lazily
inside the functions, so the application runs without pymongo installed or MongoDB reachable.
Credentials only ever come from environment variables (MONGODB_URI).
"""
from __future__ import annotations

import json

import pandas as pd

from app.services.data_loader import normalize_cleaned_frame


class MongoUnavailableError(RuntimeError):
    """MongoDB is not configured, not reachable, or holds no data."""


def _client(uri: str, timeout_ms: int):
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise MongoUnavailableError("pymongo is not installed") from exc
    return MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)


def load_policies(uri: str, db: str, collection: str, timeout_ms: int = 3000) -> pd.DataFrame:
    """Read the cleaned policies collection into a correctly-typed DataFrame."""
    client = _client(uri, timeout_ms)
    try:
        client.admin.command("ping")
        docs = list(client[db][collection].find({}, {"_id": 0}))
    except Exception as exc:  # network, auth, DNS ... never leak the URI in the message
        raise MongoUnavailableError(f"{type(exc).__name__} while reading MongoDB") from exc
    finally:
        client.close()
    if not docs:
        raise MongoUnavailableError(f"collection '{collection}' is empty - run scripts/seed_mongodb.py")
    return normalize_cleaned_frame(pd.DataFrame(docs))


def save_policies(df: pd.DataFrame, uri: str, db: str, collection: str, timeout_ms: int = 5000) -> int:
    """Replace the collection with the cleaned data. Dates are stored as ISO strings (no NaT/NumPy encoding issues)."""
    out = df.copy()
    out["AgeBand"] = out["AgeBand"].astype(str)
    records = json.loads(out.to_json(orient="records", date_format="iso"))
    client = _client(uri, timeout_ms)
    try:
        coll = client[db][collection]
        coll.delete_many({})
        coll.insert_many(records)
        coll.create_index("PolicyNumber", unique=True)
    except Exception as exc:
        raise MongoUnavailableError(f"{type(exc).__name__} while writing MongoDB") from exc
    finally:
        client.close()
    return len(records)
