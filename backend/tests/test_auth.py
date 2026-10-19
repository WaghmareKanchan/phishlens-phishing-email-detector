import time

import pyotp

from app.core import security
from tests.conftest import make_user


def test_health_and_first_user_is_admin(client, admin, user):
    assert client.get("/health").json() == {"status": "ok"}
    assert admin["user"]["is_admin"] is True
    assert user["user"]["is_admin"] is False


def test_timestamps_are_utc_with_z(client, user):
    """Bug fix: naive timestamps made browsers show the wrong time (5h30 off in India)."""
    assert user["user"]["created_at"].endswith("Z")


def test_login_ok_and_wrong_password_and_unknown_email_look_the_same(client, user):
    ok = client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]})
    assert ok.status_code == 200 and ok.json()["two_factor_required"] is False
    bad = client.post("/api/auth/login", json={"email": user["email"], "password": "WrongPass1"})
    ghost = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "WrongPass1"})
    assert bad.status_code == ghost.status_code == 401
    assert bad.json()["detail"] == ghost.json()["detail"]


def test_duplicate_email_and_validation_messages(client, user):
    r = client.post("/api/auth/register", json={"name": "X Y", "email": user["email"], "password": "Password123"})
    assert r.status_code == 409
    r = client.post("/api/auth/register", json={"name": "X Y", "email": "a@b.co", "password": "alllettersnodigit"})
    assert r.status_code == 422 and "password" in r.json()["errors"]


def test_password_is_bcrypt_and_whole_password_counts(client):
    """Bug fix: bcrypt silently ignores everything after byte 72."""
    h = security.hash_password("A1" + "x" * 100 + "END1")
    assert h.startswith("$2b$")
    assert security.verify_password("A1" + "x" * 100 + "END1", h)
    assert not security.verify_password("A1" + "x" * 100 + "END2", h)


def test_login_is_rate_limited(client, user):
    """Bug fix: unlimited password guessing."""
    codes = [client.post("/api/auth/login", json={"email": user["email"], "password": "bad%d" % i}).status_code
             for i in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    r = client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_change_password_invalidates_old_tokens(client, user):
    r = client.post("/api/auth/change-password", headers=user["h"],
                    json={"current_password": "nope", "new_password": "NewPass123"})
    assert r.status_code == 400 and r.json()["code"] == "wrong_password"      # not 401 -> no auto logout
    r = client.post("/api/auth/change-password", headers=user["h"],
                    json={"current_password": user["password"], "new_password": "NewPass123"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=user["h"]).status_code == 401    # old token dead
    new_h = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert client.get("/api/auth/me", headers=new_h).status_code == 200
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "NewPass123"}).status_code == 200


def test_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["code"] == "session_expired"
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def _enable_2fa(client, u):
    setup = client.post("/api/auth/2fa/setup", headers=u["h"]).json()
    assert set(setup) == {"otpauth_uri", "qr_svg"}        # the raw secret is NOT sent as a separate field
    assert setup["qr_svg"].startswith("<svg")             # QR drawn by the server: works without internet
    assert 'viewBox="0 0 ' in setup["qr_svg"]             # scalable: never cropped (a cropped QR cannot be scanned)
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    totp = pyotp.parse_uri(setup["otpauth_uri"])
    assert client.post("/api/auth/2fa/confirm", headers=u["h"], json={"code": "000000"}).status_code == 400
    r = client.post("/api/auth/2fa/confirm", headers=u["h"], json={"code": totp.now()})
    assert r.status_code == 200 and r.json() == {"ok": True}   # no backup codes in the answer
    return totp


def test_2fa_full_flow_with_replay_protection(client, user):
    totp = _enable_2fa(client, user)

    login = client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]}).json()
    assert login["two_factor_required"] is True and login["access_token"] is None
    assert login["two_factor_setup_required"] is False
    tmp = login["temp_token"]
    # the temp token must NOT work as a session
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + tmp}).status_code == 401

    assert client.post("/api/auth/2fa/verify", json={"temp_token": tmp, "code": "123456"}).status_code == 401
    future = totp.at(time.time() + 30)      # next window: newer than the one used at confirm
    ok = client.post("/api/auth/2fa/verify", json={"temp_token": tmp, "code": future})
    assert ok.status_code == 200 and ok.json()["user"]["two_factor_enabled"] is True
    # replaying the same code must fail (bug fix: codes could be reused inside their window)
    again = client.post("/api/auth/2fa/verify", json={"temp_token": tmp, "code": future})
    assert again.status_code == 401


def test_login_without_2fa_asks_to_set_it_up_every_time(client, user):
    """Skipping 2FA is allowed, but the user is asked again at every login until it is on."""
    for _ in range(3):
        r = client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]}).json()
        assert r["two_factor_required"] is False and r["two_factor_setup_required"] is True
        assert r["access_token"]            # they are logged in even if they skip
    _enable_2fa(client, user)
    r = client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]}).json()
    assert r["two_factor_required"] is True and r["two_factor_setup_required"] is False


def test_2fa_cannot_be_turned_off_and_no_backup_codes(client, user):
    from app.database import engine
    from sqlalchemy import inspect
    totp = _enable_2fa(client, user)
    for path in ("/api/auth/2fa/disable", "/api/auth/2fa/backup-codes/regenerate"):
        assert client.post(path, headers=user["h"], json={"code": totp.at(time.time() + 30)}).status_code in (404, 405)
    assert client.get("/api/auth/2fa/backup-codes/remaining", headers=user["h"]).status_code in (404, 405)
    assert "backup_codes" not in inspect(engine).get_table_names()      # nothing about backup codes is stored
    assert client.post("/api/auth/2fa/setup", headers=user["h"]).status_code == 409   # cannot restart / replace it
    r = client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]}).json()
    assert r["two_factor_required"] is True


def test_2fa_verify_is_rate_limited(client, user):
    _enable_2fa(client, user)
    from app.core.rate_limit import ALL_LIMITERS
    for lim in ALL_LIMITERS:   # the wrong code sent during setup shares the per-user allowance
        lim.clear()
    tmp = client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]}).json()["temp_token"]
    codes = [client.post("/api/auth/2fa/verify", json={"temp_token": tmp, "code": "%06d" % i}).status_code for i in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_password_minimum_is_six_characters(client):
    ok = client.post("/api/auth/register", json={"name": "Six Chars", "email": "six@example.com", "password": "abc123"})
    assert ok.status_code == 201
    short = client.post("/api/auth/register", json={"name": "Five Chars", "email": "five@example.com", "password": "abc12"})
    assert short.status_code == 422 and "password" in short.json()["errors"]


def test_forgot_and_reset_password(client, user):
    r = client.post("/api/auth/forgot-password", json={"email": user["email"]}).json()
    code = r["dev_code"]
    assert code and len(code) == 6
    # unknown account: same message, no code
    ghost = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"}).json()
    assert ghost["dev_code"] is None and "ghost@example.com" in ghost["message"]

    bad = client.post("/api/auth/reset-password", json={"email": user["email"], "code": "000000" if code != "000000" else "111111", "new_password": "Brand123new"})
    assert bad.status_code == 400 and "tries left" in bad.json()["detail"]
    ok = client.post("/api/auth/reset-password", json={"email": user["email"], "code": code, "new_password": "Brand123new"})
    assert ok.status_code == 200
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "Brand123new"}).status_code == 200
    assert client.get("/api/auth/me", headers=user["h"]).status_code == 401           # old sessions signed out
    # a code works only once
    again = client.post("/api/auth/reset-password", json={"email": user["email"], "code": code, "new_password": "Other123pass"})
    assert again.status_code == 400


def test_reset_code_locks_after_too_many_wrong_tries(client, user):
    code = client.post("/api/auth/forgot-password", json={"email": user["email"]}).json()["dev_code"]
    wrong = "000000" if code != "000000" else "111111"
    last = None
    for _ in range(5):
        last = client.post("/api/auth/reset-password", json={"email": user["email"], "code": wrong, "new_password": "Brand123new"})
    assert last.json()["code"] == "reset_locked"
    good = client.post("/api/auth/reset-password", json={"email": user["email"], "code": code, "new_password": "Brand123new"})
    assert good.status_code == 400    # real code is dead too: must request a new one
