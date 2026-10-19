"""Loads every trained model found in the artifacts directory ONCE and keeps it in memory."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Sequence

from .predictors import SPECS, ModelSpec, Predictor, Row, make_predictor

log = logging.getLogger("phishlens.ml")


class ModelRegistry:
    def __init__(self):
        self._predictors: dict[str, Predictor] = {}
        self.errors: dict[str, str] = {}
        self._lock = threading.RLock()

    def load(self, artifacts_dir: Path) -> None:
        """(Re)load. A missing file is normal (model not trained yet); a broken file is logged and skipped."""
        loaded, errors = {}, {}
        for spec in SPECS:
            p = make_predictor(spec, artifacts_dir)
            if not p.path.exists():
                continue
            try:
                p.load()
                loaded[spec.name] = p
                log.info("loaded model %s from %s", spec.name, p.path.name)
            except Exception as exc:  # noqa: BLE001  one bad model must not take the API down
                errors[spec.name] = f"{type(exc).__name__}: {exc}"
                log.error("could not load %s: %s", spec.name, errors[spec.name])
        with self._lock:
            self._predictors, self.errors = loaded, errors

    # ---------- queries ----------
    @property
    def loaded_names(self) -> list[str]:
        with self._lock:
            return [s.name for s in SPECS if s.name in self._predictors]

    def is_loaded(self, name: str) -> bool:
        with self._lock:
            return name in self._predictors

    def predict(self, rows: Sequence[Row]) -> dict[str, list[float]]:
        """{model name: [P(phishing) per row]} for every loaded model that works."""
        with self._lock:
            items = list(self._predictors.items())
        out = {}
        for name, predictor in items:
            try:
                out[name] = predictor.predict_proba(rows)
            except Exception as exc:  # noqa: BLE001
                log.exception("prediction failed for %s: %s", name, exc)
                self.errors[name] = f"{type(exc).__name__}: {exc}"
        return out


registry = ModelRegistry()
