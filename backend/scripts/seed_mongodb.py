"""Upload the cleaned dataset to MongoDB (requires MONGODB_URI in .env and `pip install pymongo[srv]`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.services.data_loader import read_cleaned_csv  # noqa: E402
from app.services.mongo_store import save_policies  # noqa: E402

if __name__ == "__main__":
    s = get_settings()
    if not s.mongodb_uri:
        sys.exit("MONGODB_URI is not set (see .env.example).")
    n = save_policies(read_cleaned_csv(s.cleaned_data_path), s.mongodb_uri, s.mongodb_db, s.mongodb_collection)
    print(f"Inserted {n:,} policies into {s.mongodb_db}.{s.mongodb_collection}")
