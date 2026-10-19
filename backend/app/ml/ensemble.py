"""Combines the individual models into one verdict.

Normal mode   : every loaded trained model scores the e-mail; the ensemble is their plain average.
                (If you prefer, weight by each model's F1 from metrics.json - one line to change.)
Fallback mode : NO trained model is available -> a single rule-based score is returned and
                engine == "heuristic" so the UI can say so. Nothing is ever presented as ML when it isn't.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .heuristics import analyze_signals, fallback_score
from .predictors import SPECS
from .registry import ModelRegistry, registry as default_registry

PHISH_AT = 0.70
WARN_AT = 0.40
FALLBACK_NAME = "Rules (fallback)"


def band(p: float) -> str:
    return "phish" if p >= PHISH_AT else "warn" if p >= WARN_AT else "safe"


@dataclass
class EmailAnalysis:
    ensemble_score: float
    verdict: str
    engine: str                       # "trained" | "heuristic"
    predictions: list = field(default_factory=list)   # [{model_name, model_type, score, verdict}]
    evidence: list = field(default_factory=list)
    body_segments: list = field(default_factory=list)
    models_loaded: int = 0
    models_expected: int = len(SPECS)


def analyze_many(rows: Sequence[tuple], reg: ModelRegistry | None = None) -> list[EmailAnalysis]:
    """rows = [(sender, subject, body), ...]. Models are called ONCE for the whole batch."""
    reg = reg or default_registry
    rows = list(rows)
    signals = [analyze_signals(*r) for r in rows]
    scores = reg.predict(rows) if rows else {}
    types = {s.name: s.type for s in SPECS}

    results = []
    for i, sig in enumerate(signals):
        if scores:
            preds = [{"model_name": n, "model_type": types[n], "score": round(v[i], 4), "verdict": band(v[i])}
                     for n, v in scores.items()]
            ens = sum(p["score"] for p in preds) / len(preds)
            engine = "trained"
        else:
            s = fallback_score(sig)
            preds = [{"model_name": FALLBACK_NAME, "model_type": "RULES", "score": round(s, 4), "verdict": band(s)}]
            ens, engine = s, "heuristic"
        ens = round(ens, 4)
        results.append(EmailAnalysis(ensemble_score=ens, verdict=band(ens), engine=engine, predictions=preds,
                                     evidence=sig.evidence, body_segments=sig.segments,
                                     models_loaded=len(scores)))
    return results


def analyze_one(sender: str, subject: str, body: str, reg: ModelRegistry | None = None) -> EmailAnalysis:
    return analyze_many([(sender, subject, body)], reg)[0]
