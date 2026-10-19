"""Load + clean + split a labelled e-mail CSV."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from app.ml.labels import normalize_label

# Column names found in popular public phishing datasets -> our names
ALIASES = {
    "sender": ["sender", "from", "from_address", "sender_email"],
    "subject": ["subject", "email_subject"],
    "body": ["body", "text", "email_text", "message", "content", "email_body"],
    "label": ["label", "class", "type", "email_type", "target", "phishing", "is_phishing", "spam"],
}


def _norm(c: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_")


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Return a DataFrame with columns sender, subject, body, label (1 = phishing, 0 = legitimate)."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding_errors="replace")
    cols = {_norm(c): c for c in raw.columns}
    pick = {k: next((cols[a] for a in names if a in cols), None) for k, names in ALIASES.items()}
    if pick["body"] is None or pick["label"] is None:
        raise SystemExit(f"{path}: need a body/text column and a label column. Found: {list(raw.columns)}")

    df = pd.DataFrame({
        "sender": raw[pick["sender"]] if pick["sender"] else "",
        "subject": raw[pick["subject"]] if pick["subject"] else "",
        "body": raw[pick["body"]],
        "label": raw[pick["label"]].map(normalize_label),
    })
    n0 = len(df)
    df = df[df["label"] != ""]
    unknown = n0 - len(df)
    df["label"] = (df["label"] == "phishing").astype(int)
    for c in ("sender", "subject", "body"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    df = df[(df["subject"] + df["body"]).str.len() > 0]
    # Remove exact duplicates BEFORE splitting: the same e-mail in train and test inflates every metric.
    key = (df["subject"] + "\x1f" + df["body"]).map(lambda t: hashlib.md5(t.encode("utf-8", "ignore")).hexdigest())
    before = len(df)
    df = df.loc[~key.duplicated()].reset_index(drop=True)
    print(f"[data] {n0} rows read | {unknown} dropped (unknown label) | {before - len(df)} duplicates removed | "
          f"{len(df)} kept | phishing share {df['label'].mean():.1%}")
    if df["label"].nunique() < 2:
        raise SystemExit("The dataset must contain both phishing and legitimate e-mails.")
    return df


def split(df: pd.DataFrame, seed: int = 42):
    """70 % train / 10 % validation / 20 % test, stratified, fixed seed (same split every run)."""
    train_val, test = train_test_split(df, test_size=0.20, stratify=df["label"], random_state=seed)
    train, val = train_test_split(train_val, test_size=0.125, stratify=train_val["label"], random_state=seed)
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)
