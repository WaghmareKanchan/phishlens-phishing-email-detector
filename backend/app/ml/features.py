"""Numeric features for the Random Forest (the same counters the evidence panel is built from)."""
from __future__ import annotations

import numpy as np

from .heuristics import FEATURE_NAMES, analyze_signals


def numeric_features(sender: str, subject: str, body: str) -> list[float]:
    return analyze_signals(sender, subject, body).features


def numeric_matrix(df) -> np.ndarray:
    """df: pandas DataFrame with columns sender, subject, body."""
    return np.asarray([numeric_features(s, su, b) for s, su, b in zip(df["sender"], df["subject"], df["body"])],
                      dtype=float)


__all__ = ["FEATURE_NAMES", "numeric_features", "numeric_matrix"]
