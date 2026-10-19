"""Turns (sender, subject, body) into ONE normalised string.

The very same function is imported by the training scripts and by the API, so the model sees
identical text at training time and at prediction time (otherwise accuracy silently drops in
production: "training/serving skew").
"""
from __future__ import annotations

import html
import re

MAX_CHARS = 20_000  # very long bodies add cost, not accuracy

_SCRIPT_STYLE = re.compile(r"(?is)<(script|style)\b.*?</\1>")
_TAG = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_WS = re.compile(r"\s+")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def clean_html(text: str) -> str:
    text = _SCRIPT_STYLE.sub(" ", text or "")
    text = _TAG.sub(" ", text)
    return html.unescape(text)


def _url_tokens(match: re.Match) -> str:
    """Replace a URL by generic tokens. The full domain is dropped on purpose: public datasets are
    often collected from different sources for each class (e.g. Enron = legitimate), so a literal
    domain would let the model "cheat" by memorising the source instead of learning phishing."""
    url = match.group(0).rstrip(".,;:!?)]}>'\"")
    host = re.sub(r"^https?://", "", url, flags=re.I).split("/")[0].split(":")[0].lower()
    toks = ["urltoken"]
    if _IPV4.match(host):
        toks.append("urlip")
    elif "." in host:
        toks.append("tld_" + host.rsplit(".", 1)[-1])
    if url.lower().startswith("http://"):
        toks.append("urlhttp")
    if "-" in host:
        toks.append("urlhyphen")
    if len(host.split(".")) > 3:
        toks.append("urldeepsub")
    return " " + " ".join(toks) + " "


def build_text(sender: str, subject: str, body: str) -> str:
    body = clean_html((body or "")[:MAX_CHARS * 2])
    body = _URL.sub(_url_tokens, body)[:MAX_CHARS]
    subject = clean_html(subject or "")

    sender_tokens = ""
    addr = re.search(r"<([^>]+)>", sender or "")
    addr_s = (addr.group(1) if addr else (sender or "")).strip().lower()
    if "@" in addr_s:
        dom = addr_s.split("@")[-1]
        sender_tokens = "senderdomain_tld_" + dom.rsplit(".", 1)[-1] if "." in dom else ""
        if "-" in dom:
            sender_tokens += " senderhyphen"
    text = _YEAR.sub(" yeartoken ", f"{subject} . {body}") + " " + sender_tokens   # era is not evidence of phishing
    return _WS.sub(" ", text).strip().lower()
