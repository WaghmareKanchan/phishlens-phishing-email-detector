"""Rule-based signals: the human-readable EVIDENCE shown in the UI, the highlighted spans in the
e-mail body, and the raw counts reused as numeric features by the Random Forest.

This module does not decide the verdict when trained models are loaded; it explains it.
If no trained model is available it is used as a (clearly labelled) fallback score.

Differences from the first version of this file (all were real bugs):
  * keyword regexes now use word boundaries ("hotpot" no longer matches "otp", "catalog install"
    no longer matches "log in")
  * "won't" no longer counts as the prize word "won"
  * trailing punctuation is stripped from URLs ("http://x.com)." -> "http://x.com")
  * a subject made only of digits is not a "shouting subject"
  * highlights are returned as text SEGMENTS, not character offsets (Python counts code points,
    JavaScript counts UTF-16 units, so offsets break on emoji)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

URGENCY = r"urgent(?:ly)?|immediately|within 24 hours|suspended|final notice|act now|expires?|last chance"
CREDENTIAL = r"verify|confirm your|passwords?|login details|log ?in|card number|otp"
REWARD = r"winner|won(?!['\u2019]t)|lottery|prize|gift card|claim|free|reward"

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd"}
BAD_TLDS = (".xyz", ".top", ".click", ".zip", ".work", ".info")
BRANDS = ("hdfc", "sbi", "paypal", "amazon", "microsoft", "apple", "google", "netflix")

_URG_RX = re.compile(rf"\b(?:{URGENCY})\b", re.I)
_CRED_RX = re.compile(rf"\b(?:{CREDENTIAL})\b", re.I)
_REW_RX = re.compile(rf"\b(?:{REWARD})\b", re.I)
_URL_PATTERN = r"https?://[^\s<>\"']+"
_URL_RX = re.compile(_URL_PATTERN, re.I)
_SEGMENT_RX = re.compile(
    rf"(?P<url>{_URL_PATTERN})|\b(?P<urg>{URGENCY})\b|\b(?P<cred>{CREDENTIAL})\b|\b(?P<rew>{REWARD})\b", re.I)
_TRAILING = ".,;:!?)]}>'\""
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_SENDER = re.compile(r'^\s*"?([^"<]*?)"?\s*<([^>]+)>\s*$')

FEATURE_NAMES = [
    "n_urgency", "n_credential", "n_reward", "generic_greeting", "shouty_subject",
    "n_urls", "n_ip_urls", "n_shorteners", "n_http_urls", "n_bad_tld_urls", "n_lookalike_urls",
    "brand_mismatch", "sender_lookalike", "sender_bad_tld",
    "exclam_count", "upper_ratio", "log_body_len", "n_distinct_hosts", "has_html",
]


def iter_urls(text: str):
    """Yield (start, end, url) with trailing punctuation removed."""
    for m in _URL_RX.finditer(text or ""):
        url = m.group(0).rstrip(_TRAILING)
        if url:
            yield m.start(), m.start() + len(url), url


def url_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


@dataclass
class Signals:
    cats: dict = field(default_factory=lambda: {"text": 0.0, "links": 0.0, "sender": 0.0})
    evidence: list = field(default_factory=list)
    segments: list = field(default_factory=list)
    features: list = field(default_factory=list)


def _ev(category: str, severity: str, title: str, detail: str) -> dict:
    return {"category": category, "severity": severity, "title": title, "detail": detail}


def _words(matches) -> str:
    return ", ".join(sorted({m.lower() for m in matches}))


def split_body_segments(body: str) -> list[dict]:
    """Cut the body into [{text, kind}] where kind is url | urg | cred | rew | None."""
    segs, last = [], 0
    for m in _SEGMENT_RX.finditer(body or ""):
        kind = m.lastgroup
        start, end = m.start(), m.end()
        if kind == "url":
            end = start + len(m.group(0).rstrip(_TRAILING))
            if end == start:
                continue
        if start > last:
            segs.append({"text": body[last:start], "kind": None})
        segs.append({"text": body[start:end], "kind": kind})
        last = end
    if last < len(body or ""):
        segs.append({"text": body[last:], "kind": None})
    return segs


def analyze_signals(sender: str, subject: str, body: str) -> Signals:
    sender, subject, body = sender or "", subject or "", body or ""
    sig = Signals()
    cats, ev = sig.cats, sig.evidence
    text = f"{subject}\n{body}"

    urg = _URG_RX.findall(text)
    cred = _CRED_RX.findall(text)
    rew = _REW_RX.findall(text)
    if urg:
        cats["text"] += min(28, len(urg) * 10)
        ev.append(_ev("text", "high" if len(urg) > 2 else "med", "Pressure and urgency",
                      "Phrases that push you to act fast: " + _words(urg)))
    if cred:
        cats["text"] += min(26, len(cred) * 13)
        ev.append(_ev("text", "high", "Asks for sensitive details", "Mentions: " + _words(cred)))
    if rew:
        cats["text"] += min(24, len(rew) * 8)
        ev.append(_ev("text", "med", "Reward or prize language", "Mentions: " + _words(rew)))

    generic = bool(re.search(r"dear (customer|user|member|account holder)", body, re.I))
    if generic:
        cats["text"] += 8
        ev.append(_ev("text", "low", "Generic greeting", "The email does not address you by name."))

    has_letters = any(c.isalpha() for c in subject)
    shouty = bool(re.search(r"!{2,}", subject) or (len(subject) > 8 and has_letters and subject == subject.upper()))
    if shouty:
        cats["text"] += 6
        ev.append(_ev("text", "low", "Shouting subject line", "Excess capitals or exclamation marks."))

    # ---- links ----
    n_urls = n_ip = n_short = n_http = n_tld = n_look = 0
    hosts = set()
    for _s, _e, url in iter_urls(body):
        n_urls += 1
        host = url_host(url)
        hosts.add(host)
        if _IPV4.match(host):
            n_ip += 1
            cats["links"] += 25
            ev.append(_ev("links", "high", "Link uses a raw IP address", f"{host} is not a normal website name."))
        if host in SHORTENERS:
            n_short += 1
            cats["links"] += 15
            ev.append(_ev("links", "med", "Shortened link", f"{host} hides the real destination."))
        if url.lower().startswith("http://"):
            n_http += 1
            cats["links"] += 8
            ev.append(_ev("links", "low", "Link is not encrypted", f"{url[:60]} uses http, not https."))
        if host.endswith(BAD_TLDS):
            n_tld += 1
            cats["links"] += 12
            ev.append(_ev("links", "med", "Unusual domain ending", f"{host} ends in a TLD often used for throwaway sites."))
        if re.search(r"(secure|verify|login|update)", host) and "-" in host:
            n_look += 1
            cats["links"] += 15
            ev.append(_ev("links", "high", "Look-alike domain", f"{host} mixes security words with hyphens."))

    # ---- sender ----
    m = _SENDER.match(sender)
    name = m.group(1).strip().lower() if m else ""
    addr = (m.group(2) if m else sender).strip().lower()
    domain = addr.split("@")[-1] if "@" in addr else ""
    brand = next((b for b in BRANDS if b in name), None)
    brand_mismatch = bool(brand and brand not in domain)
    if brand_mismatch:
        cats["sender"] += 22
        ev.append(_ev("sender", "high", "Sender name does not match domain",
                      f"Name says \u201c{brand}\u201d but the address comes from {domain or 'an unknown domain'}."))
    s_look = bool(domain and re.search(r"(secure|verify|login|support|alert)", domain) and "-" in domain)
    if s_look:
        cats["sender"] += 16
        ev.append(_ev("sender", "med", "Suspicious sender domain", f"{domain} looks made up to seem official."))
    s_tld = bool(domain and domain.endswith(BAD_TLDS))
    if s_tld:
        cats["sender"] += 10
        ev.append(_ev("sender", "med", "Sender uses an unusual domain ending", domain))

    if not ev:
        ev.append(_ev("text", "low", "No warning signs found",
                      "No pressure language, risky links or sender mismatches."))

    letters = [c for c in subject + body if c.isalpha()]
    upper_ratio = (sum(c.isupper() for c in letters) / len(letters)) if letters else 0.0
    sig.features = [
        len(urg), len(cred), len(rew), float(generic), float(shouty),
        n_urls, n_ip, n_short, n_http, n_tld, n_look,
        float(brand_mismatch), float(s_look), float(s_tld),
        (subject + body).count("!"), upper_ratio, math.log1p(len(body)), len(hosts),
        float(bool(re.search(r"<\s*(html|body|div|a\s|table)", body, re.I))),
    ]
    sig.segments = split_body_segments(body)
    return sig


def fallback_score(sig: Signals) -> float:
    """0..1 risk from the rule counts. NOT machine learning; used only when no trained model is loaded."""
    raw = sig.cats["text"] + sig.cats["links"] + sig.cats["sender"]
    return 1 / (1 + math.exp(-(raw - 35) / 12))
