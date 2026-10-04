"""Convert pandas/NumPy results into plain JSON-safe Python (NaN/NaT -> None, Timestamps -> ISO strings)."""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd


def to_builtin(obj):
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_builtin(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [to_builtin(v) for v in obj.tolist()]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if (math.isnan(obj) or math.isinf(obj)) else float(obj)
    if obj is pd.NaT:
        return None
    if isinstance(obj, (pd.Timestamp, dt.datetime)):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, dt.date):
        return obj.isoformat()
    if obj is pd.NA:
        return None
    return obj
