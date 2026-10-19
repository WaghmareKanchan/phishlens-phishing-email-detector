"""Trains the classic models on the synthetic demo set and checks the whole serve path."""
import json
from pathlib import Path

import pytest

from app.ml.ensemble import analyze_many
from app.ml.registry import ModelRegistry
from app.services import model_service
from ml_training import train as trainer


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    d = tmp_path_factory.mktemp("art")
    assert trainer.main(["--demo", "--models", "nb", "rf", "--artifacts", str(d)]) == 0
    return d


def test_training_writes_artifacts_and_metrics(artifacts):
    meta = json.loads((artifacts / "metrics.json").read_text())
    assert meta["dataset"] == "synthetic-demo" and meta["n_test"] > 0
    assert set(meta["models"]) == {"Naive Bayes", "Random Forest"}
    tn, fp, fn, tp = meta["models"]["Naive Bayes"]["confusion_matrix"]
    assert tn + fp + fn + tp == meta["n_test"]
    assert (artifacts / "naive_bayes.joblib").exists() and (artifacts / "random_forest.joblib").exists()


def test_registry_ensemble_and_demo_flag(artifacts, client):
    reg = ModelRegistry()
    reg.load(artifacts)
    assert reg.loaded_names == ["Naive Bayes", "Random Forest"]
    phish, safe = analyze_many([
        ("PayPal <a@paypal-verify.xyz>", "URGENT verify", "Dear Customer verify your password http://185.2.2.2/a act now"),
        ("Priya <p@college.edu>", "Project review", "Hi team, the review moved to Thursday at 3 pm."),
    ], reg)
    assert phish.engine == "trained" and phish.models_loaded == 2 and len(phish.predictions) == 2
    assert phish.ensemble_score > safe.ensemble_score and phish.verdict == "phish" and safe.verdict == "safe"

    from app.database import SessionLocal
    with SessionLocal() as db:
        model_service.sync_models(db, reg, artifacts)
        out = model_service.list_models(db, reg)
        nb = next(m for m in out.models if m.name == "Naive Bayes")
        assert nb.trained and nb.n_test > 0 and nb.is_real is False       # demo data is never "real"
        assert "DEMO" in out.notice
        model_service.sync_models(db, ModelRegistry(), artifacts)         # restore: nothing loaded
