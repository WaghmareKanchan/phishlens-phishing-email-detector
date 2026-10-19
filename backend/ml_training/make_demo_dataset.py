"""Generates a SYNTHETIC labelled e-mail CSV so you can smoke-test the whole pipeline in a minute.

!! The e-mails are built from templates, so any model will score ~100 % on them. Those numbers say
!! nothing about real-world accuracy. Use a real dataset for real results (see README).

    python -m ml_training.make_demo_dataset --out data/demo_emails.csv --n 3000
"""
from __future__ import annotations

import argparse
import random

import pandas as pd

BRANDS = ["HDFC Bank", "SBI", "PayPal", "Amazon", "Microsoft", "Apple", "Netflix", "Google"]
BAD_TLD = ["xyz", "top", "click", "work", "info"]
SHORT = ["bit.ly/3x", "tinyurl.com/a1", "t.co/Zq"]
NAMES = ["Priya", "Rahul", "Anita", "Karan", "Meera", "Vikram", "Sana", "Arjun"]
PH_SUBJ = ["URGENT: Your {b} account will be suspended", "Action required: verify your {b} login",
           "You won a {n} gift card!!!", "Your parcel could not be delivered", "Final notice: payment failed",
           "Security alert on your {b} account", "Claim your reward before it expires", "Unusual sign-in detected"]
PH_BODY = ["Dear Customer,\n\nWe detected unusual activity. You must verify your password and confirm your card number "
           "immediately or your account will be suspended.\n\nLog in now: {url}\n",
           "Dear User,\n\nYou are the lucky winner of our monthly lottery. Claim your free prize before it expires. "
           "Act now!\n\n{url}\n\nWe only need your login details to release the reward.",
           "Hello,\n\nYour package is waiting. Please confirm your address and pay the small redelivery fee within 24 hours.\n{url}",
           "Your payment could not be processed. Update your billing details to avoid interruption: {url}\nThis is your last chance.",
           "We noticed a sign-in from a new device. If this was not you, secure your account here: {url}"]
LG_SUBJ = ["Project review moved to {d}", "Minutes from yesterday's meeting", "Lunch on Friday?", "Invoice {n} for your records",
           "Your order has shipped", "Re: question about the report", "Weekly newsletter", "Photos from the trip",
           "Server maintenance tonight", "Please review the draft"]
LG_BODY = ["Hi team,\n\nThe review is now on {d} at 3 pm in Room 204. Please bring the latest version of your report.\n\nThanks,\n{p}",
           "Hi {p},\n\nAttached are the minutes. Let me know if I missed anything. The agenda is in the shared folder.\n\nBest,\n{q}",
           "Hey,\n\nAre you free for lunch on Friday? There is a new place near the office.\n{q}",
           "Hello {p},\n\nThanks for your order. It shipped today and should arrive in 3-5 days. Track it at {safe}\n\nRegards,\nSupport",
           "Hi all,\n\nURGENT: planned server maintenance tonight at 11 pm. Please save your work and log out. No action is needed afterwards.\n\nIT desk",
           "Please verify the numbers in section 3 of the draft before Thursday; I think the totals are off by one.\n\n{q}"]


def _pick(rng, xs):
    return xs[rng.randrange(len(xs))]


def make(n: int, seed: int = 7) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        phish = i % 2 == 0
        p, q = _pick(rng, NAMES), _pick(rng, NAMES)
        if phish:
            b = _pick(rng, BRANDS)
            kind = rng.random()
            url = (f"http://{rng.randrange(11, 250)}.{rng.randrange(1, 250)}.{rng.randrange(1, 250)}.{rng.randrange(1, 250)}/verify" if kind < .25
                   else f"https://{_pick(rng, SHORT)}" if kind < .45
                   else f"http://{b.split()[0].lower()}-secure-login.{_pick(rng, BAD_TLD)}/update?id={rng.randrange(99999)}")
            dom = f"alerts@{b.split()[0].lower()}-{_pick(rng, ['secure', 'verify', 'support'])}.{_pick(rng, BAD_TLD)}" if rng.random() < .7 else "noreply@mail-service.com"
            sender = f"{b} Security <{dom}>"
            subject = _pick(rng, PH_SUBJ).format(b=b, n=f"${rng.randrange(100, 2000)}")
            body = _pick(rng, PH_BODY).format(url=url)
        else:
            d = _pick(rng, ["Monday", "Tuesday", "Thursday", "Friday"])
            sender = f"{p} {_pick(rng, ['Nair', 'Shah', 'Iyer', 'Rao'])} <{p.lower()}@{_pick(rng, ['college.edu', 'company.com', 'gmail.com'])}>"
            subject = _pick(rng, LG_SUBJ).format(d=d, n=rng.randrange(1000, 9999))
            body = _pick(rng, LG_BODY).format(d=d, p=p, q=q, safe="https://www.amazon.in/orders")
        rows.append({"sender": sender, "subject": subject, "body": body + f"\n\nRef {rng.randrange(10**6)}",
                     "label": "phishing" if phish else "legitimate"})
    rng.shuffle(rows)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/demo_emails.csv")
    ap.add_argument("--n", type=int, default=3000)
    a = ap.parse_args()
    make(a.n).to_csv(a.out, index=False)
    print(f"wrote {a.n} synthetic e-mails to {a.out}  (SYNTHETIC: metrics from it are meaningless)")
