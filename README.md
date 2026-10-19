# PhishLens

**An explainable machine-learning and deep-learning ensemble for phishing e-mail detection, with an audit of shortcut learning in public e-mail corpora.**

PhishLens is a full-stack web application that triages e-mails as *safe*, *suspicious* or *phishing*. It averages the probabilities of three different classifiers, shows rule-based evidence for every verdict, and ships with a hardened authentication layer and an automated test suite. This repository is the reference implementation that accompanies the research paper listed under [Citation](#citation).

![Python](https://img.shields.io/badge/python-3.10--3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688) ![Tests](https://img.shields.io/badge/tests-42%20passed-brightgreen)

---

## Why this project

Many phishing detectors report 97-99% accuracy on a single public corpus. On such corpora the phishing and legitimate e-mails come from *different collections*, so a model can score highly by recognising the collection (formatting, era, mailing list) instead of phishing behaviour. PhishLens does two things:

1. **A usable system**, not just a notebook: authentication, explanations, batch scanning, history and an admin console.
2. **An honest evaluation**: bootstrap confidence intervals, McNemar tests, cross-validation, ablations, strong linear baselines and a *shortcut audit* that measures how much accuracy comes from artefacts.

## Key results (held-out test set, n = 2,159)

| Model | Accuracy | F1 | ROC-AUC | False positives | False negatives |
|---|---|---|---|---|---|
| Naive Bayes (TF-IDF) | 98.38% | 97.18% | 0.9982 | 1 | 34 |
| Random Forest (TF-IDF + 19 rule features) | 98.70% | 97.75% | 0.9995 | 1 | 27 |
| BiLSTM | 98.38% | 97.30% | 0.9982 | 29 | 6 |
| **Ensemble (NB + RF + BiLSTM)** | **99.17%** | **98.57%** | **0.9998** | 2 | 16 |
| Linear SVM (reference baseline) | 99.17% | 98.58% | 0.9994 | 5 | 13 |

> **Read this before trusting the numbers.** A linear SVM matches the ensemble, so the ensemble's benefit is operational (transparent combination, per-model scores, graceful degradation), not statistical. A shortcut audit shows that a one-line "no capital letters" rule reaches 74.7% accuracy on this corpus. In-corpus accuracy is therefore an **upper bound** on real-world performance. See the paper for details.

## Features

- **Three-model ensemble** with a three-level verdict: `>= 0.70` phishing, `0.40-0.70` suspicious, otherwise safe.
- **Explainable evidence**: highlighted urgency phrases, credential requests, risky links and sender mismatches from a rule engine (19 numeric features).
- **Web interface**: single e-mail analysis, CSV batch scan, history, saved e-mails, model metrics and an admin console.
- **Security hardening**: bcrypt passwords, revocable JWTs, TOTP two-factor authentication, rate limiting, same-origin CORS.
- **Tested**: 42 automated tests pass (1 skipped).
- **Honest by design**: without trained models, results are labelled *"Rule-based result, not machine learning"*.

## Architecture

The code follows an MVC layout on both sides.

```
phishlens/
├── frontend/                 VIEW: HTML, CSS, JS (models / views / controllers)
└── backend/
    ├── app/
    │   ├── models/           SQLAlchemy tables (User, Email, Analysis, Prediction, ...)
    │   ├── schemas/          Pydantic data contracts
    │   ├── controllers/      FastAPI routers (auth, email, analysis, models, admin)
    │   ├── services/         business rules
    │   ├── core/             security (bcrypt, JWT, TOTP), rate limiter
    │   └── ml/               preprocessing, rule engine, predictors, ensemble
    ├── ml_training/          training, evaluation and dataset scripts
    ├── artifacts/            trained model files and metrics.json
    ├── data/                 dataset location (see below)
    └── tests/                API / unit tests and a browser end-to-end test
```

Request flow: browser view → JS controller → JS model → HTTP → FastAPI controller → service → ORM model → SQLite.

## Quick start

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open <http://127.0.0.1:8000>. API docs are at <http://127.0.0.1:8000/docs>. The first registered account becomes the admin.

## Dataset

The training corpus has **10,793 e-mails** (3,180 phishing, 7,613 legitimate) built from two public sources:

- Phishing: [rf-peixoto/phishing_pot](https://github.com/rf-peixoto/phishing_pot)
- Legitimate: SpamAssassin / Enron ham from [anastasiaarsky/ML-Capstone-Spam-Classification](https://github.com/anastasiaarsky/ML-Capstone-Spam-Classification)

The corpus contains **real phishing e-mails** and should be handled as sensitive. Rebuild it yourself with:

```bash
python -m ml_training.build_dataset      # downloads about 1 GB, writes data/emails.csv
```

To train on your own data, provide a CSV with columns `body`, `label` and optionally `sender`, `subject`. Accepted labels: `phishing/legitimate`, `phish/ham`, `spam/ham`, `1/0`.

## Training and evaluation

```bash
pip install -r requirements-ml.txt       # TensorFlow / Keras
python -m ml_training.train --data data/emails.csv --dataset-name "phishing_pot + SpamAssassin ham"
```

Training removes duplicates, makes a stratified 70/10/20 split with a fixed seed, trains each model, evaluates every *saved* file through the same loader the API uses, and writes `artifacts/` and `metrics.json`. Restart the API or use **Admin > Reload models** afterwards.

BERT fine-tuning is supported (`--models bert`) but is **not part of the reported results**.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests -q                                      # backend tests
playwright install chromium && pytest tests/e2e -q   # browser end-to-end test
```

## Security design

- Passwords: bcrypt (cost 12) over a SHA-256 pre-hash, avoiding the 72-byte truncation. A dummy hash is checked for unknown accounts to prevent timing-based enumeration.
- Sessions: HS256 JWTs with a per-user token version, so a password change revokes old tokens.
- Two-factor authentication: TOTP with replay protection (last accepted time step) and atomic backup-code consumption.
- Rate limiting on login, 2FA, password reset and registration.
- Reset codes use keyed HMAC-SHA-256. CORS is same-origin by default.

**The service has not been independently penetration-tested.**

## Production checklist

- Set `ENV=production` and a strong `SECRET_KEY` (the server refuses to start without it).
- Set `FIRST_USER_IS_ADMIN=false` and `ADMIN_EMAILS=you@example.com`.
- Run behind HTTPS with `uvicorn --proxy-headers`.
- Configure `SMTP_*` so password-reset codes are e-mailed.
- Rate limiting is in process memory. With several workers, move it to Redis.
- `.joblib` and `.keras` files can execute code when loaded. Only load model files you trained yourself or trust.
- Never commit your `.env` file or secret keys.

## Known limitations

- One source-confounded corpus and no external validation in the published results.
- Heterogeneous labels: phishing mixed with scams and adverts. English only.
- No sender/header evidence in training, so the three sender rules are never exercised.
- Explanations are rule-based and are not a faithful account of the ensemble's decision.
- No adversarial or AI-generated-phishing evaluation. Calibration and band thresholds are untuned.

## Citation

If you use this work, please cite:

```bibtex
@article{waghmare2026phishlens,
  title   = {PhishLens: An explainable machine-learning and deep-learning ensemble framework for phishing e-mail detection, with an audit of shortcut learning in public e-mail corpora},
  author  = {Waghmare, Kanchan Dhondiba and Khan, S.},
  year    = {2026},
  note    = {Manuscript submitted for publication}
}
```

## Authors

- **Kanchan Dhondiba Waghmare**, Department of Computer Science and Engineering (Cyber Security), P.E.S. College of Engineering, Chhatrapati Sambhajinagar, India
- **S. Khan**, same department (supervisor)

## Acknowledgements

AI assistance (Claude, Anthropic) was used to generate code from the authors' design and logic and to help with drafting. The authors designed, reviewed, tested and deployed the system and take full responsibility for it.

## License

This project's source code is released under the [MIT License](LICENSE). The datasets listed above are **not** covered by this license; they remain under the terms of their original sources.