import io
import json
import time

from tests.conftest import make_user

PHISH = dict(sender="HDFC Bank <alerts@hdfcbank-secure-login.com>", subject="URGENT: account suspended",
             body="Dear Customer, verify your password now: http://hdfc-verify.secure-login.xyz/u")
SAFE = dict(sender="Priya <priya@college.edu>", subject="Project review moved", body="Hi team, review is Thursday 3 pm.")


# ───────── analysis ─────────
def test_analyze_without_trained_models_is_honest_about_it(client, user):
    r = client.post("/api/analyze", headers=user["h"], json=PHISH)
    assert r.status_code == 200
    d = r.json()
    assert d["engine"] == "heuristic" and d["models_loaded"] == 0
    assert d["predictions"][0]["model_type"] == "RULES"
    assert d["verdict"] == "phish" and d["evidence"] and any(s["kind"] == "url" for s in d["body_segments"])
    assert client.post("/api/analyze", headers=user["h"], json=SAFE).json()["verdict"] == "safe"


def test_analyze_requires_login_and_body(client, user):
    assert client.post("/api/analyze", json=PHISH).status_code == 401
    assert client.post("/api/analyze", headers=user["h"], json={"body": ""}).status_code == 422


def test_history_keeps_sender_and_subject_of_unsaved_emails(client, user):
    """Bug fix: history/admin showed blank sender+subject unless the e-mail had been saved."""
    client.post("/api/analyze", headers=user["h"], json=PHISH)
    h = client.get("/api/history", headers=user["h"]).json()
    assert len(h) == 1 and h[0]["subject"] == PHISH["subject"] and h[0]["sender"] == PHISH["sender"]
    assert h[0]["analyzed_at"].endswith("Z")


def test_clear_history_hides_but_admin_totals_stay(client, admin, user):
    before = client.get("/api/admin/stats", headers=admin["h"]).json()["total_analyses"]
    client.post("/api/analyze", headers=user["h"], json=SAFE)
    client.delete("/api/history", headers=user["h"])
    assert client.get("/api/history", headers=user["h"]).json() == []
    assert client.get("/api/admin/stats", headers=admin["h"]).json()["total_analyses"] == before + 1


def test_users_only_see_their_own_data(client, user):
    other = make_user(client)
    client.post("/api/analyze", headers=user["h"], json=PHISH)
    assert client.get("/api/history", headers=other["h"]).json() == []


# ───────── saved e-mails ─────────
def test_email_crud_and_ownership(client, user):
    e = client.post("/api/emails", headers=user["h"], json={**SAFE, "label": "legitimate"})
    assert e.status_code == 201
    eid = e.json()["id"]
    assert [x["id"] for x in client.get("/api/emails", headers=user["h"]).json()] == [eid]

    other = make_user(client)
    assert client.put(f"/api/emails/{eid}", headers=other["h"], json=SAFE).status_code == 404
    assert client.delete(f"/api/emails/{eid}", headers=other["h"]).status_code == 404

    up = client.put(f"/api/emails/{eid}", headers=user["h"], json={**SAFE, "subject": "Changed", "label": "phishing"})
    assert up.json()["subject"] == "Changed" and up.json()["label"] == "phishing"
    assert client.delete(f"/api/emails/{eid}", headers=user["h"]).status_code == 204
    assert client.get("/api/emails", headers=user["h"]).json() == []


def test_invalid_label_rejected(client, user):
    assert client.post("/api/emails", headers=user["h"], json={**SAFE, "label": "maybe"}).status_code == 422


def test_saved_email_keeps_verdict_of_the_exact_text_only(client, user):
    a = client.post("/api/analyze", headers=user["h"], json=PHISH).json()
    e = client.post("/api/emails", headers=user["h"], json={**PHISH, "analysis_id": a["analysis_id"]}).json()
    assert e["last_verdict"] == a["verdict"] and e["last_analyzed_at"].endswith("Z")
    # editing the text drops the stale verdict
    e2 = client.put(f"/api/emails/{e['id']}", headers=user["h"], json={**PHISH, "body": PHISH["body"] + " edited"}).json()
    assert e2["last_verdict"] is None
    # an analysis of DIFFERENT text must not be attached
    e3 = client.post("/api/emails", headers=user["h"], json={**SAFE, "analysis_id": a["analysis_id"]}).json()
    assert e3["last_verdict"] is None
    # someone else's analysis id must not be attachable either
    other = make_user(client)
    e4 = client.post("/api/emails", headers=other["h"], json={**PHISH, "analysis_id": a["analysis_id"]}).json()
    assert e4["last_verdict"] is None


def test_analyze_with_email_id_updates_saved_verdict(client, user):
    e = client.post("/api/emails", headers=user["h"], json=PHISH).json()
    r = client.post("/api/analyze", headers=user["h"], json={**PHISH, "email_id": e["id"]}).json()
    assert r["email_id"] == e["id"]
    assert client.get("/api/emails", headers=user["h"]).json()[0]["last_verdict"] == r["verdict"]
    # edited text -> not linked
    r2 = client.post("/api/analyze", headers=user["h"], json={**SAFE, "email_id": e["id"]}).json()
    assert r2["email_id"] is None
    assert client.post("/api/analyze", headers=user["h"], json={**PHISH, "email_id": "nope"}).status_code == 404


def test_analyze_save_flag(client, user):
    r = client.post("/api/analyze", headers=user["h"], json={**PHISH, "save": True, "label": "phishing"}).json()
    assert r["email_id"]
    assert len(client.get("/api/emails", headers=user["h"]).json()) == 1


# ───────── batch ─────────
def _csv(text):
    return {"file": ("emails.csv", io.BytesIO(text.encode("utf-8")), "text/csv")}


def test_batch_ok_and_bulk_save(client, user):
    text = ('sender,subject,body,label\n'
            '"HDFC <a@hdfcbank-secure-login.com>","URGENT","verify your password http://185.1.1.1/x","Phishing"\n'
            'priya@college.edu,Meeting,"Hi, review on Thursday.\nBring your report.",ham\n'
            'x@y.com,Empty,,\n')
    r = client.post("/api/analyze/batch", headers=user["h"], files=_csv(text))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["skipped_empty"] == 1 and len(d["results"]) == 2 and d["truncated"] is False
    assert [x["verdict"] for x in d["results"]] == ["phish", "safe"]
    assert [x["label"] for x in d["results"]] == ["phishing", "legitimate"]
    assert len(client.get("/api/history", headers=user["h"]).json()) == 2

    payload = {"emails": [{"sender": x["sender"], "subject": x["subject"], "body": x["body"], "label": x["label"],
                           "analysis_id": x["analysis_id"]} for x in d["results"]]}
    assert client.post("/api/emails/bulk", headers=user["h"], json=payload).json() == {"saved": 2}
    saved = client.get("/api/emails", headers=user["h"]).json()
    assert {s["last_verdict"] for s in saved} == {"phish", "safe"}


def test_batch_edge_cases(client, user):
    # No file-size limit and no row cap: a 6 MB file with 30 000 rows is scanned completely.
    big = "body\n" + "\n".join(f"row {i} hello " + "x" * 200 for i in range(30_000))
    assert len(big) > 6 * 1024 * 1024
    r = client.post("/api/analyze/batch", headers=user["h"], files=_csv(big))
    assert r.status_code == 200
    d = r.json()
    assert len(d["results"]) == 30_000 and d["truncated"] is False

    assert client.post("/api/analyze/batch", headers=user["h"], files=_csv("a,b\n1,2\n")).status_code == 400
    assert client.post("/api/analyze/batch", headers=user["h"], files=_csv("")).status_code == 400
    semi = client.post("/api/analyze/batch", headers=user["h"], files=_csv("subject;body\nhi;urgent verify your password\n"))
    assert semi.status_code == 200 and len(semi.json()["results"]) == 1          # ; delimiter (Excel in many countries)
    long_body = "x" * 200_000                                                      # > default csv field limit
    assert client.post("/api/analyze/batch", headers=user["h"], files=_csv(f"body\n{long_body}\n")).status_code == 200
    cp = {"file": ("e.csv", io.BytesIO("body\ncaf\xe9 urgent\n".encode("cp1252")), "text/csv")}
    assert client.post("/api/analyze/batch", headers=user["h"], files=cp).status_code == 200
    assert client.post("/api/analyze/batch", files=_csv("body\nx\n")).status_code == 401


# ───────── models + admin + page ─────────
def test_batch_accepts_any_line_ending(client, user):
    """Bug fix: 'new-line character seen in unquoted field' for CSVs with bare CR line endings."""
    for name, text in {
        "bare CR (old Mac)": "sender,subject,body\rbob@x.com,Hi,hello there\rann@x.com,Yo,verify your password now\r",
        "CR inside unquoted field": "sender,subject,body\nbob@x.com,Hi,line one\rline two\n",
        "CRLF (Windows/Excel)": "sender,subject,body\r\nbob@x.com,Hi,hello\r\n",
        "quoted multi-line body": 'sender,subject,body\r\nbob@x.com,Hi,"line one\r\nline two"\r\n',
    }.items():
        r = client.post("/api/analyze/batch", headers=user["h"], files=_csv(text))
        assert r.status_code == 200 and len(r.json()["results"]) >= 1, (name, r.text)


def test_models_endpoint_without_artifacts(client):
    d = client.get("/api/models").json()
    assert d["engine"] == "heuristic" and "rule-based" in d["notice"]
    assert [m["name"] for m in d["models"]] == ["Naive Bayes", "Random Forest", "LSTM", "BERT"]
    assert all(m["trained"] is False and m["accuracy"] == 0 for m in d["models"])


def test_admin_endpoints_are_admin_only(client, admin, user):
    for path in ("/api/admin/stats", "/api/admin/users", "/api/admin/activity"):
        assert client.get(path, headers=user["h"]).status_code == 403
        assert client.get(path).status_code == 401
        assert client.get(path, headers=admin["h"]).status_code == 200
    assert client.post("/api/admin/models/reload", headers=user["h"]).status_code == 403


def test_admin_activity_has_names_and_subjects(client, admin, user):
    client.post("/api/analyze", headers=user["h"], json=PHISH)
    act = client.get("/api/admin/activity", headers=admin["h"]).json()
    assert act[0]["subject"] == PHISH["subject"] and act[0]["user"] == user["user"]["name"]
    users = client.get("/api/admin/users", headers=admin["h"]).json()
    assert any(u["email"] == user["email"] for u in users)


def test_cors_does_not_reflect_arbitrary_origins(client):
    r = client.options("/api/models", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_page_and_static_are_served_with_csp(client):
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Content-Security-Policy" in r.headers and r.headers["X-Frame-Options"] == "DENY"
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/api/models").headers["Cache-Control"] == "no-store"
