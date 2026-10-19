"""Uniform wrapper around every saved model: .load() once, then .predict_proba(rows) -> P(phishing).

`rows` is always a list of (sender, subject, body) tuples.
"""
from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .preprocessing import build_text

log = logging.getLogger("phishlens.ml")
Row = tuple  # (sender, subject, body)


@dataclass(frozen=True)
class ModelSpec:
    name: str       # shown in the UI and used as the key everywhere
    type: str       # "ML" | "DL"
    filename: str   # inside the artifacts directory
    kind: str       # "sklearn" | "keras"


SPECS = [
    ModelSpec("Naive Bayes", "ML", "naive_bayes.joblib", "sklearn"),
    ModelSpec("Random Forest", "ML", "random_forest.joblib", "sklearn"),
    ModelSpec("LSTM", "DL", "lstm.keras", "keras"),
    ModelSpec("BERT", "DL", "bert.keras", "keras"),
]


class Predictor(ABC):
    def __init__(self, spec: ModelSpec, path: Path):
        self.spec, self.path = spec, path

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def predict_proba(self, rows: Sequence[Row]) -> list[float]: ...


class SklearnPredictor(Predictor):
    def load(self) -> None:
        import joblib  # SECURITY: joblib/pickle can run code on load. Only ever load files YOU trained.
        self.pipeline = joblib.load(self.path)
        self.phish_idx = list(self.pipeline.classes_).index(1)

    def predict_proba(self, rows):
        import pandas as pd
        df = pd.DataFrame(list(rows), columns=["sender", "subject", "body"])
        return [float(p) for p in self.pipeline.predict_proba(df)[:, self.phish_idx]]


class KerasPredictor(Predictor):
    """LSTM and BERT. Both are saved as a single .keras file that already contains its own text
    vectoriser / tokenizer, so inference is just model.predict(list_of_strings)."""

    def load(self) -> None:
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
        import keras
        try:
            import keras_hub  # noqa: F401  (registers the BERT classes so the file can be deserialised)
        except ImportError:
            if self.spec.name == "BERT":
                raise
        from .keras_compat import utf8_text_files   # Windows: vocabulary.txt must be read as UTF-8
        with utf8_text_files():
            self.model = keras.saving.load_model(self.path, compile=False)
        self._lock = threading.Lock()  # one predict at a time per model
        self._fn = None
        import tensorflow as tf       # a compiled graph is much faster than eager calls
        self._fn = tf.function(lambda x: self.model(x, training=False))
        self._is_bert = self.spec.name == "BERT"

    def predict_proba(self, rows):
        texts = np.array([build_text(*r) for r in rows], dtype=object)
        if len(texts) == 0:
            return []
        with self._lock:
            chunks = []
            for i in range(0, len(texts), 32):
                batch = texts[i:i + 32]
                if self._is_bert:   # BERT task model: run its tokenizer first, then the compiled network
                    batch = self.model.preprocessor(list(batch))
                chunks.append(np.asarray(self._fn(batch)))
            out = np.concatenate(chunks)
        return [float(p) for p in (out[:, 1] if out.ndim == 2 and out.shape[1] == 2 else out.reshape(-1))]


def make_predictor(spec: ModelSpec, artifacts_dir: Path) -> Predictor:
    cls = SklearnPredictor if spec.kind == "sklearn" else KerasPredictor
    return cls(spec, Path(artifacts_dir) / spec.filename)
