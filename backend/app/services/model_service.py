"""Keeps the ml_models table in sync with what is actually on disk / in memory."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..ml.ensemble import FALLBACK_NAME
from ..ml.predictors import SPECS
from ..ml.registry import ModelRegistry
from ..models import MLModel
from ..schemas.model_info import ModelInfoOut, ModelsOut

log = logging.getLogger("phishlens.models")
METRICS_FILE = "metrics.json"
DEMO_DATASET = "synthetic-demo"


def _read_metrics(artifacts_dir: Path) -> dict:
    path = Path(artifacts_dir) / METRICS_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("could not read %s", path)
        return {}


def ensure_rows(db: Session) -> dict[str, MLModel]:
    """Make sure one row exists per model (+ the fallback pseudo-model). Returns {name: row}."""
    rows = {m.name: m for m in db.query(MLModel).all()}
    wanted = [(s.name, s.type) for s in SPECS] + [(FALLBACK_NAME, "RULES")]
    for name, type_ in wanted:
        if name not in rows:
            rows[name] = MLModel(name=name, type=type_)
            db.add(rows[name])
    db.commit()
    return rows


def sync_models(db: Session, registry: ModelRegistry, artifacts_dir: Optional[Path] = None) -> None:
    artifacts_dir = artifacts_dir or get_settings().artifacts_dir
    rows = ensure_rows(db)
    meta = _read_metrics(artifacts_dir)
    per_model = meta.get("models", {})
    dataset = str(meta.get("dataset", ""))

    for spec in SPECS:
        row = rows[spec.name]
        row.trained = registry.is_loaded(spec.name)
        m = per_model.get(spec.name) if row.trained else None
        if m:
            tn, fp, fn, tp = m.get("confusion_matrix", [0, 0, 0, 0])
            row.accuracy, row.precision = float(m["accuracy"]), float(m["precision"])
            row.recall, row.f1 = float(m["recall"]), float(m["f1"])
            row.tn, row.fp, row.fn, row.tp = int(tn), int(fp), int(fn), int(tp)
            row.latency_ms = float(m.get("latency_ms", 0.0))
            row.n_test = int(meta.get("n_test", 0))
            row.dataset = dataset
            row.is_real = dataset != DEMO_DATASET
            ts = meta.get("trained_at")
            try:
                row.trained_at = datetime.fromisoformat(ts) if ts else None
                if row.trained_at and row.trained_at.tzinfo is None:
                    row.trained_at = row.trained_at.replace(tzinfo=timezone.utc)
            except ValueError:
                row.trained_at = None
        else:   # not loaded (or no metrics): never show stale or invented numbers
            row.accuracy = row.precision = row.recall = row.f1 = row.latency_ms = 0.0
            row.tn = row.fp = row.fn = row.tp = row.n_test = 0
            row.dataset, row.is_real, row.trained_at = "", False, None
    db.commit()


def list_models(db: Session, registry: ModelRegistry) -> ModelsOut:
    rows = ensure_rows(db)
    ordered = [rows[s.name] for s in SPECS]
    loaded = [r for r in ordered if r.trained]
    notice = None
    if not loaded:
        notice = ("No trained models are loaded, so every result comes from a simple rule-based fallback, "
                  "not machine learning. Train the models (see the README) and then reload them.")
    elif any(not r.is_real for r in loaded):
        notice = ("These models were trained on the synthetic DEMO dataset, so their scores and the numbers "
                  "below are not meaningful. Train on a real labelled dataset (see the README).")
    elif len(loaded) < len(ordered):
        notice = f"Only {len(loaded)} of {len(ordered)} models are loaded; the ensemble uses just those."
    return ModelsOut(engine="trained" if loaded else "heuristic", notice=notice,
                     models=[ModelInfoOut.model_validate(r) for r in ordered])
