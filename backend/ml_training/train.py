"""Train the four models, evaluate them on a held-out test set, save artifacts + metrics.json.

    cd backend
    python -m ml_training.train --data data/emails.csv --dataset-name "Kaggle Phishing Email Dataset"
    python -m ml_training.train --data data/emails.csv --models nb rf          # only the classic models
    python -m ml_training.train --demo                                         # synthetic smoke test

Afterwards restart the API (or log in as admin and use "Reload models" / POST /api/admin/models/reload).
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from app.config import get_settings
from app.ml.predictors import SPECS, make_predictor
from app.ml.preprocessing import build_text
from app.ml.sklearn_models import make_naive_bayes, make_random_forest

from .datasets import load_dataset, split
from .evaluate import evaluate

KEY = {"nb": "Naive Bayes", "rf": "Random Forest", "lstm": "LSTM", "bert": "BERT"}
SPEC = {s.name: s for s in SPECS}
DEMO_NAME = "synthetic-demo"   # model_service marks anything trained on this as NOT real


def _texts(df):
    return [build_text(s, su, b) for s, su, b in zip(df["sender"], df["subject"], df["body"])]


def train_sklearn(name, make, train_df, val_df, art_dir):
    import pandas as pd
    fit_df = pd.concat([train_df, val_df], ignore_index=True)   # no early stopping needed -> use both
    pipe = make()
    pipe.fit(fit_df[["sender", "subject", "body"]], fit_df["label"])
    joblib.dump(pipe, art_dir / SPEC[name].filename, compress=3)


def train_keras(name, train_df, val_df, art_dir, args):
    import keras
    from . import keras_models as km
    keras.utils.set_random_seed(args.seed)
    tr = train_df.sample(n=min(len(train_df), args.max_train_dl), random_state=args.seed) \
        if args.max_train_dl else train_df
    x_tr, x_val = _texts(tr), _texts(val_df)
    if name == "LSTM":
        model = km.build_lstm(x_tr)
        km.fit(model, x_tr, tr["label"], x_val, val_df["label"], epochs=args.epochs_lstm, batch_size=64)
    else:
        model = km.build_bert(x_tr, preset=None if args.bert_preset == "none" else args.bert_preset,
                              seq_len=args.bert_seq_len)
        km.fit(model, x_tr, tr["label"], x_val, val_df["label"], epochs=args.epochs_bert, batch_size=args.bert_batch)
    from app.ml.keras_compat import utf8_text_files   # Windows: write the vocabulary as UTF-8
    with utf8_text_files():
        model.save(art_dir / SPEC[name].filename)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="CSV with sender/subject/body/label columns (see README)")
    ap.add_argument("--dataset-name", default=None, help="name stored in metrics.json and shown in the UI")
    ap.add_argument("--demo", action="store_true", help="generate + use a SYNTHETIC dataset (smoke test only)")
    ap.add_argument("--models", nargs="+", default=["nb", "rf", "lstm", "bert"], choices=list(KEY))
    ap.add_argument("--artifacts", default=None, help="output folder (default: backend/artifacts)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs-lstm", type=int, default=6)
    ap.add_argument("--epochs-bert", type=int, default=3)
    ap.add_argument("--bert-preset", default="bert_tiny_en_uncased",
                    help="keras-hub preset, e.g. bert_small_en_uncased / bert_base_en_uncased; 'none' = tiny scratch "
                         "model for OFFLINE smoke tests only")
    ap.add_argument("--bert-seq-len", type=int, default=128)
    ap.add_argument("--bert-batch", type=int, default=16)
    ap.add_argument("--max-train-dl", type=int, default=0,
                    help="cap the number of training e-mails for LSTM/BERT (0 = all). Handy on CPU.")
    args = ap.parse_args(argv)

    np.random.seed(args.seed)
    art_dir = Path(args.artifacts) if args.artifacts else get_settings().artifacts_dir
    art_dir.mkdir(parents=True, exist_ok=True)

    if args.demo:
        from .make_demo_dataset import make
        import tempfile
        csv_path = Path(tempfile.gettempdir()) / "phishlens_demo.csv"
        make(3000).to_csv(csv_path, index=False)
        data_path, dataset = csv_path, DEMO_NAME
        print("!! DEMO MODE: synthetic data. The resulting numbers are meaningless; do not report them.")
    elif args.data:
        data_path, dataset = Path(args.data), args.dataset_name or Path(args.data).stem
        if dataset == DEMO_NAME:
            raise SystemExit(f"'{DEMO_NAME}' is reserved for synthetic data. Pick another --dataset-name.")
    else:
        raise SystemExit("Give --data path/to/emails.csv (or --demo for a smoke test).")

    df = load_dataset(data_path)
    train_df, val_df, test_df = split(df, args.seed)
    print(f"[split] train {len(train_df)} | val {len(val_df)} | test {len(test_df)}")

    old = {}
    meta_path = art_dir / "metrics.json"
    if meta_path.exists():
        try:
            old = json.loads(meta_path.read_text())
        except ValueError:
            old = {}
    same_run = old.get("dataset") == dataset and old.get("n_test") == len(test_df) and old.get("seed") == args.seed
    models_metrics = dict(old.get("models", {})) if same_run else {}
    if old and not same_run:
        stale = [n for n in KEY.values() if (art_dir / SPEC[n].filename).exists() and n not in [KEY[m] for m in args.models]]
        if stale:
            print(f"[warn] dataset/split changed: {stale} on disk were trained on the OLD data and have no metrics "
                  "now. Retrain them too (or delete the files).")

    for key in args.models:
        name = KEY[key]
        print(f"\n=== training {name} ===")
        if name == "Naive Bayes":
            train_sklearn(name, make_naive_bayes, train_df, val_df, art_dir)
        elif name == "Random Forest":
            train_sklearn(name, make_random_forest, train_df, val_df, art_dir)
        else:
            try:
                train_keras(name, train_df, val_df, art_dir, args)
            except ImportError as exc:
                print(f"\n[SKIPPED] {name} was NOT trained because a library is missing: {exc}\n"
                      f"          Python {platform.python_version()}. Install the deep-learning libraries with\n"
                      "              pip install -r requirements-ml.txt\n"
                      "          (TensorFlow has no wheels for very new Python versions; Python 3.10-3.12 is the safest choice.)")
                continue
            except Exception as exc:  # noqa: BLE001  e.g. BERT weights could not be downloaded (no internet)
                print(f"\n[FAILED] {name} was NOT trained: {type(exc).__name__}: {exc}")
                if name == "BERT":
                    print("         BERT downloads its pre-trained weights once (needs internet). Try again online, or use\n"
                          "         --bert-preset none for a tiny from-scratch model (offline smoke test only).")
                if name == "LSTM":
                    print("         Windows tip: run  set PYTHONUTF8=1  before training.")
                continue
        # evaluate the SAVED file through the production loader
        predictor = make_predictor(SPEC[name], art_dir)
        predictor.load()
        m = evaluate(predictor, test_df)
        models_metrics[name] = m
        print(f"[{name}] acc {m['accuracy']}%  prec {m['precision']}%  rec {m['recall']}%  f1 {m['f1']}%  "
              f"cm[TN,FP,FN,TP]={m['confusion_matrix']}  {m['latency_ms']} ms/email")

    try:
        import tensorflow as tf, keras, keras_hub  # noqa: E401
        versions = {"tensorflow": tf.__version__, "keras": keras.__version__, "keras_hub": keras_hub.__version__}
    except ImportError:
        versions = {}
    import sklearn
    meta = {
        "dataset": dataset, "n_total": len(df), "n_train": len(train_df), "n_val": len(val_df),
        "n_test": len(test_df), "phishing_share": round(float(df["label"].mean()), 4), "seed": args.seed,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "sklearn": sklearn.__version__, **versions,
        "models": models_metrics,
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"\nSaved models + {meta_path}. Restart the API or use Admin > Reload models.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
