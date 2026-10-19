"""Builds data/emails.csv from two public GitHub sources (no account / API key needed).

  phishing  <- rf-peixoto/phishing_pot            real phishing .eml files (read straight from the zip)
  legitimate<- anastasiaarsky/ML-Capstone-Spam-Classification  FullData.csv.zip, rows with Label 0
               (Enron + SpamAssassin ham)

    python -m ml_training.build_dataset            # ~1 GB download, a few minutes

Honest caveats (also printed at the end):
  * The two classes come from DIFFERENT collections, which can leak "source" instead of "phishing".
    To reduce that we keep English-only mail and drop the sender column (the ham has none).
  * Legitimate mail is mostly Enron (2001) / SpamAssassin ham; the phishing is recent. Expect real-world
    accuracy on modern e-mail to be LOWER than the test-set numbers. Add your own mail for better results.
"""
from __future__ import annotations

import argparse
import csv
import email
import email.policy
import io
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from app.ml.preprocessing import clean_html

PHISH_URL = "https://codeload.github.com/rf-peixoto/phishing_pot/zip/refs/heads/main"
HAM_URL = "https://raw.githubusercontent.com/anastasiaarsky/ML-Capstone-Spam-Classification/main/FullData.csv.zip"
MAX_BODY = 8000
STOP = {"the", "and", "you", "your", "to", "of", "is", "for", "this", "with", "that", "are", "we", "on", "in", "it",
        "a", "be", "will", "have", "our", "if", "or", "as", "at", "from", "by", "not", "can", "please"}


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"[skip] {dest} already downloaded")
        return dest
    print(f"[download] {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    return dest


def is_english(text: str) -> bool:
    """Plain English prose only: mostly ASCII, real stop-WORDS (not fragments of random letters),
    and no long unbroken strings (base64 / tracking blobs would be learnt as 'gibberish = phishing')."""
    if len(text) < 60:
        return False
    if sum(c < "\x80" for c in text) / len(text) < 0.97:
        return False
    tokens = text.lower().split()
    if len(tokens) < 12:
        return False
    long_chars = sum(len(t) for t in tokens if len(t) > 30)
    if long_chars / max(1, len(text)) > 0.25:
        return False
    words = [t.strip(".,;:!?()[]<>\"'") for t in tokens]
    return sum(w in STOP for w in words) / len(words) >= 0.08


def parse_eml(raw: bytes):
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    subject = str(msg.get("subject", "") or "").strip()
    body = ""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is not None:
        try:
            body = part.get_content()
        except Exception:  # noqa: BLE001  broken charset etc.
            body = ""
        if part.get_content_type() == "text/html":
            body = clean_html(body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    # the repo tags many subjects/bodies with its own name: a pure label leak, remove it
    subject = re.sub(r"(?i)\bphishing@pot\b:?\s*", "", subject).strip()
    body = re.sub(r"(?i)\bphishing@pot\b", "", body)
    return subject, body


def build(out: Path, workdir: Path) -> None:
    # ---- phishing ----
    pz = download(PHISH_URL, workdir / "phishing_pot.zip")
    phish, seen, bad = [], 0, 0
    with zipfile.ZipFile(pz) as z:
        for name in z.namelist():
            if not name.endswith(".eml"):
                continue
            seen += 1
            try:
                subject, body = parse_eml(z.read(name))
            except Exception:  # noqa: BLE001
                bad += 1
                continue
            if is_english(subject + " " + body):
                phish.append(("", subject[:300], body[:MAX_BODY], "phishing"))
    print(f"[phishing] {seen} .eml files | {bad} unreadable | {len(phish)} kept (English with a text body)")

    # ---- legitimate ----
    hz = download(HAM_URL, workdir / "fulldata.zip")
    with zipfile.ZipFile(hz) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv") and "__MACOSX" not in n)
        csv.field_size_limit(10_000_000)
        ham_df = pd.read_csv(io.BytesIO(z.read(name)), dtype=str, keep_default_na=False)
    ham_df = ham_df[ham_df["Label"].str.strip().isin(["0", "0.0"])]
    # The Enron company e-mails (names, "ect", "hou") would be learnt as "legitimate" purely by source.
    enron = re.compile(r"enron|\bect\b|\bhou\b|\bpst\b|kaminski|\bvince\b|"
                       r"ilug|linux\.ie|listmaster|\bdaren\b|\bhpl\b|\bmeter\b|\bnom\b|\bcalpine\b|\bsitara\b", re.I)
    ham, dropped = [], 0
    for r in ham_df.itertuples():
        text = str(r.Subject) + " " + str(r.Message)
        if enron.search(text):
            dropped += 1
        elif is_english(text):
            ham.append(("", str(r.Subject)[:300], str(r.Message).strip()[:MAX_BODY], "legitimate"))
    print(f"[legitimate] {len(ham_df)} ham rows | {dropped} source-specific mails dropped (Enron staff, Irish Linux list) | {len(ham)} kept")

    df = pd.DataFrame(phish + ham, columns=["sender", "subject", "body", "label"])
    df = df.drop_duplicates(subset=["subject", "body"]).sample(frac=1, random_state=42).reset_index(drop=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nWrote {out}  ({len(df)} emails, {out.stat().st_size / 1e6:.1f} MB)")
    print(df["label"].value_counts().to_string())
    print("\nREMINDER: classes come from different sources (see the file's docstring). Do not quote the test "
          "accuracy as real-world accuracy.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/emails.csv")
    ap.add_argument("--workdir", default="data/_downloads", help="where the zips are cached")
    a = ap.parse_args()
    build(Path(a.out), Path(a.workdir))
