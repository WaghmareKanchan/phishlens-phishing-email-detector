"""Evaluate a model through the SAME Predictor class the API uses (no train/serve skew)."""
from __future__ import annotations

import statistics
import time

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score


def evaluate(predictor, test_df, threshold: float = 0.5) -> dict:
    rows = list(zip(test_df["sender"], test_df["subject"], test_df["body"]))
    y = test_df["label"].to_numpy()
    p = np.asarray(predictor.predict_proba(rows))
    pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()

    # latency of ONE e-mail (what a user waits for), median of 30 single calls after a warm-up
    predictor.predict_proba(rows[:1])
    times = []
    for r in rows[:30]:
        t0 = time.perf_counter()
        predictor.predict_proba([r])
        times.append((time.perf_counter() - t0) * 1000)

    return {
        "accuracy": round(100 * accuracy_score(y, pred), 2),
        "precision": round(100 * precision_score(y, pred, zero_division=0), 2),
        "recall": round(100 * recall_score(y, pred, zero_division=0), 2),
        "f1": round(100 * f1_score(y, pred, zero_division=0), 2),
        "confusion_matrix": [int(tn), int(fp), int(fn), int(tp)],   # [TN, FP, FN, TP]
        "latency_ms": round(statistics.median(times), 2),
    }
