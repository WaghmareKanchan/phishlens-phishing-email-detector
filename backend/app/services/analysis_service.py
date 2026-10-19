"""Business rules for analysing e-mails (single + CSV batch) and for the history list."""
from __future__ import annotations

import csv
import io
from typing import Optional

from sqlalchemy.orm import Session

from ..config import get_settings
from ..core.exceptions import AppError
from ..ml.ensemble import EmailAnalysis, analyze_many, analyze_one
from ..ml.labels import normalize_label
from ..models import Analysis, Email, MLModel, Prediction, User, utcnow
from ..schemas import analysis as s
from ..schemas.email import MAX_BODY, MAX_SENDER, MAX_SUBJECT
from . import email_service, model_service

csv.field_size_limit(2_000_000)   # the default (131 072) makes long e-mail bodies crash the parser

_SENDER_KEYS = ("sender", "from")
_SUBJECT_KEYS = ("subject",)
_BODY_KEYS = ("body", "text", "message", "email_text")
_LABEL_KEYS = ("label", "class", "type")


def _record(db: Session, user: User, model_ids: dict[str, str], sender: str, subject: str, body: str,
            res: EmailAnalysis) -> Analysis:
    """Adds (does not commit) an Analysis + its per-model Predictions."""
    analysis = Analysis(user_id=user.id, sender=sender, subject=subject,
                        content_hash=email_service.content_hash(sender, subject, body),
                        ensemble_score=res.ensemble_score, verdict=res.verdict, engine=res.engine,
                        analyzed_at=utcnow())
    db.add(analysis)
    db.flush()   # gives it an id
    for p in res.predictions:
        db.add(Prediction(analysis_id=analysis.id, model_id=model_ids[p["model_name"]],
                          score=p["score"], verdict=p["verdict"]))
    return analysis


def _model_ids(db: Session) -> dict[str, str]:
    return {name: row.id for name, row in model_service.ensure_rows(db).items()}


def _to_out(res: EmailAnalysis, analysis_id: str, email_id: Optional[str]) -> s.AnalyzeOut:
    return s.AnalyzeOut(analysis_id=analysis_id, ensemble_score=res.ensemble_score, verdict=res.verdict,
                        engine=res.engine, models_loaded=res.models_loaded, models_expected=res.models_expected,
                        predictions=[s.PredictionOut(**p) for p in res.predictions],
                        evidence=[s.EvidenceOut(**e) for e in res.evidence],
                        body_segments=[s.SegmentOut(**g) for g in res.body_segments], email_id=email_id)


def analyze_single(db: Session, user: User, p: s.AnalyzeIn) -> s.AnalyzeOut:
    res = analyze_one(p.sender, p.subject, p.body)
    analysis = _record(db, user, _model_ids(db), p.sender, p.subject, p.body, res)

    email: Optional[Email] = None
    if p.email_id:
        email = email_service.get_owned(db, user, p.email_id)
        email_service.attach_analysis(email, analysis, user.id)   # no-op if the text was edited
    elif p.save:
        email = Email(owner_id=user.id, sender=p.sender, subject=p.subject, body=p.body, label=p.label)
        db.add(email)
        db.flush()
        email_service.attach_analysis(email, analysis, user.id)

    db.commit()   # analysis + predictions + email in ONE transaction
    linked = email.id if (email is not None and analysis.email_id == email.id) else None
    return _to_out(res, analysis.id, linked)


# ───────────────────────── batch ─────────────────────────
def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):   # cp1252 = what Excel writes in many countries
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise AppError(400, "The file is not valid text. Save it as a CSV (UTF-8) and try again.", code="bad_file")


def _pick(fields: dict[str, str], keys) -> Optional[str]:
    return next((fields[k] for k in keys if k in fields), None)


def parse_csv(raw: bytes) -> tuple[list[tuple], int, bool]:
    """-> (rows[(sender, subject, body, label)], skipped_empty, truncated)"""
    cfg = get_settings()
    # Python's csv module fails with "new-line character seen in unquoted field" when a line ends in a
    # bare CR (old Mac / some exporters) or a CR sits inside an unquoted field. Make every line ending
    # a plain "\n" first, so any CSV from Excel, Google Sheets, Mac or Linux can be read.
    text = _decode(raw).replace("\r\n", "\n").replace("\r", "\n")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect)
    if not reader.fieldnames:
        raise AppError(400, "No header row found in the CSV.", code="bad_file")
    fields = {f.strip().lower(): f for f in reader.fieldnames if f}
    sender_k, subject_k = _pick(fields, _SENDER_KEYS), _pick(fields, _SUBJECT_KEYS)
    body_k, label_k = _pick(fields, _BODY_KEYS), _pick(fields, _LABEL_KEYS)
    if not body_k:
        raise AppError(400, "The CSV needs at least a 'body' column.", code="bad_file")

    rows, skipped, truncated = [], 0, False
    try:
        for i, row in enumerate(reader):
            if cfg.max_batch_rows and i >= cfg.max_batch_rows:   # 0 = no cap
                truncated = True
                break
            body = (row.get(body_k) or "").strip()[:MAX_BODY]
            if not body:
                skipped += 1
                continue
            rows.append(((row.get(sender_k) or "").strip()[:MAX_SENDER] if sender_k else "",
                         (row.get(subject_k) or "").strip()[:MAX_SUBJECT] if subject_k else "",
                         body,
                         normalize_label(row.get(label_k)) if label_k else ""))
    except csv.Error as exc:
        raise AppError(400, f"Could not read the CSV: {exc}", code="bad_file")
    return rows, skipped, truncated


def analyze_batch(db: Session, user: User, raw: bytes) -> s.BatchOut:
    rows, skipped, truncated = parse_csv(raw)
    if not rows:
        raise AppError(400, "No rows with a body were found in the CSV.", code="bad_file")

    results = analyze_many([(r[0], r[1], r[2]) for r in rows])   # models run ONCE for the whole file
    ids = _model_ids(db)                                          # one query, not one per prediction
    out = []
    for i, ((sender, subject, body, label), res) in enumerate(zip(rows, results), start=1):
        a = _record(db, user, ids, sender, subject, body, res)
        out.append(s.BatchRowOut(row=i, sender=sender, subject=subject, body=body, label=label,
                                 verdict=res.verdict, ensemble_score=res.ensemble_score, analysis_id=a.id))
    db.commit()                                                   # one commit, not 500
    return s.BatchOut(engine=results[0].engine, total_rows=len(rows) + skipped, skipped_empty=skipped,
                      truncated=truncated, results=out)


# ───────────────────────── history ─────────────────────────
def history(db: Session, user: User) -> list[s.HistoryItemOut]:
    rows = (db.query(Analysis).filter_by(user_id=user.id, hidden=False)
            .order_by(Analysis.analyzed_at.desc()).limit(100).all())
    return [s.HistoryItemOut(id=a.id, sender=a.sender, subject=a.subject, verdict=a.verdict,
                             ensemble_score=a.ensemble_score, analyzed_at=a.analyzed_at) for a in rows]


def clear_history(db: Session, user: User) -> None:
    """Hides the user's history. Rows stay (flagged) so admin totals do not silently shrink."""
    db.query(Analysis).filter_by(user_id=user.id, hidden=False).update({"hidden": True})
    db.commit()
