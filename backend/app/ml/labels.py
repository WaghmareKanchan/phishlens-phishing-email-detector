"""One place that decides what a label string means (used by CSV upload AND the training scripts)."""
PHISHING = {"phishing", "phish", "phishing email", "spam", "malicious", "fraud", "1", "true", "yes"}
LEGIT = {"legitimate", "legit", "ham", "safe", "safe email", "benign", "not phishing", "0", "false", "no"}


def normalize_label(value) -> str:
    """-> "phishing" | "legitimate" | "" (unknown)."""
    v = str(value if value is not None else "").strip().lower()
    try:                      # "1.0" / "0.0" (pandas writes floats) -> "1" / "0"
        f = float(v)
        v = str(int(f)) if f == int(f) else v
    except (ValueError, OverflowError):
        pass
    if v in PHISHING:
        return "phishing"
    if v in LEGIT:
        return "legitimate"
    return ""
