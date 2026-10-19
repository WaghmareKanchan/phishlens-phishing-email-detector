"""Browser end-to-end test: real server + real Chromium driving the real UI.

    pip install playwright && playwright install chromium
    python -m pytest tests/e2e -q
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pyotp
import pytest

playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect
BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def server():
    tmp = Path(tempfile.mkdtemp(prefix="phishlens_e2e_"))
    (tmp / "art").mkdir()
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp/'e2e.db'}", "SECRET_KEY": "e2e-secret", "BCRYPT_ROUNDS": "4",
           "ARTIFACTS_DIR": str(tmp / "art"), "ENV": "development"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=BACKEND, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    import urllib.request
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/health", timeout=1); break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill(); pytest.fail("server did not start")
    yield base, tmp
    proc.terminate()


def test_full_user_journey(server):
    base, tmp = server
    csv_path = tmp / "batch.csv"
    csv_path.write_text('sender,subject,body\n"PayPal <a@paypal-verify.xyz>",URGENT,"Dear Customer verify your password http://185.9.9.9/x act now"\n'
                        'bob@college.edu,Lunch,"Are you free on Friday? I won\'t be late."\n', encoding="utf-8")
    errors = []
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        # Real problems only: uncaught JS errors, and any request to OUR server that is 5xx or a missing file.
        # (Expected 400/401/429 API answers from the deliberate wrong-password steps are fine.)
        page.on("response", lambda r: errors.append(f"{r.status} {r.url}") if r.url.startswith(base) and
                (r.status >= 500 or (r.status == 404 and "/static/" in r.url)) else None)
        page.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error"
                and "Failed to load resource" not in m.text else None)
        page.goto(base)

        # ---- register with 2FA ----
        page.click("#tabRegister")
        page.fill("#rgName", "Priya Nair"); page.fill("#rgEmail", "priya@example.com")
        page.fill("#rgPw", "Sup3rSecret!"); page.fill("#rgPw2", "Sup3rSecret!")
        with page.expect_response("**/api/auth/2fa/setup") as setup_resp:
            page.click("#registerBtn")
        page.wait_for_selector("#totpSetupForm:not([hidden])")
        uri = setup_resp.value.json()["otpauth_uri"]
        totp = pyotp.parse_uri(uri)           # the secret is only inside the QR; the page never prints it
        assert page.locator("#tsKey").count() == 0 and totp.secret not in page.inner_text("body")
        page.fill("#tsCode", "000000"); page.click("#tsConfirmBtn")
        page.wait_for_selector("#tsCodeErr:not(:empty)")
        page.fill("#tsCode", totp.now()); page.click("#tsConfirmBtn")
        page.wait_for_selector("#app:not([hidden])")                  # straight into the app: no backup codes screen
        assert page.locator("#backupRevealForm").count() == 0
        assert page.inner_text("#uName") == "Priya Nair"
        assert page.is_visible("#adminTabBtn")                       # first account = admin

        # ---- analyze a sample ----
        page.click('[data-sample="bank"]'); page.click("#analyzeBtn")
        page.wait_for_selector("#result:not([hidden]) .verdict.phish")
        assert page.locator("#result mark.url").count() >= 1 and page.locator("#result mark.urg").count() >= 1
        assert "not machine learning" in page.inner_text("#result .note")     # honest fallback notice
        page.click('[data-sample="real"]'); page.click("#analyzeBtn")
        page.wait_for_selector("#result .verdict.safe")

        # ---- save, list, open ----
        page.click('[data-sample="bank"]'); page.click("#analyzeBtn"); page.wait_for_selector("#result .verdict.phish")
        page.click("#saveBtn")
        expect(page.locator("#status")).to_contain_text("Saved at")
        page.click('[data-tab="saved"]')
        page.wait_for_selector("#savedBody tr")
        row = page.inner_text("#savedBody tr")
        assert "URGENT" in row and "Phishing" in row                         # verdict kept with the saved e-mail
        assert page.inner_text("#savedCount") == "1"
        page.click('#savedBody button[data-act="open"]')
        page.wait_for_selector("#view-analyze:not([hidden])")
        assert "URGENT" in page.input_value("#subject") and "Editing a saved email" in page.inner_text("#draftState")
        # delete needs two clicks
        page.click('[data-tab="saved"]')
        page.click('#savedBody button[data-act="del"]'); assert "Confirm delete" in page.inner_text("#savedBody")
        page.click('#savedBody button[data-act="del"]')
        page.wait_for_selector("#savedEmpty:not([hidden])")

        # ---- history shows sender + subject of every analysis ----
        page.click('[data-tab="history"]')
        page.wait_for_selector("#histBody tr")
        assert page.locator("#histBody tr").count() == 3
        assert "HDFC Bank Security" in page.inner_text("#histBody") and "Project review" in page.inner_text("#histBody")

        # ---- batch ----
        page.click('[data-tab="batch"]')
        page.set_input_files("#batchFile", str(csv_path))
        page.wait_for_selector("#batchBody tr")
        assert page.locator("#batchBody tr").count() == 2
        txt = page.inner_text("#batchBody")
        assert "Phishing" in txt and "Looks safe" in txt                     # "won't" no longer flagged as a prize
        page.click("#batchSaveAllBtn")
        expect(page.locator("#batchStatus")).to_contain_text("Saved 2")
        with page.expect_download() as dl:
            page.click("#batchExportBtn")
        assert dl.value.suggested_filename == "batch-results.csv"

        # ---- models tab (nothing trained) ----
        page.click('[data-tab="models"]')
        page.wait_for_selector("#modelsNotice:not([hidden])")
        assert "rule-based" in page.inner_text("#modelsNotice")
        assert page.locator("#metricsTable tbody tr").count() == 4 and "Not trained yet" in page.inner_text("#metricsTable")

        # ---- settings: password + 2FA status ----
        page.click('[data-tab="settings"]')
        expect(page.locator("#tfStatusText")).to_contain_text("is on")
        assert "backup" not in page.inner_text("#view-settings").lower()      # no backup codes anywhere
        assert page.locator("#tfDisableBtn").count() == 0 and page.locator("#tfEnableBtn").is_hidden()   # cannot turn it off
        page.fill("#curPw", "wrong"); page.fill("#newPw", "NewPass123"); page.fill("#newPw2", "NewPass123"); page.click("#changePwBtn")
        page.wait_for_selector("#curPwErr:not(:empty)")
        page.fill("#curPw", "Sup3rSecret!"); page.click("#changePwBtn")
        page.wait_for_selector("#pwOk:not([hidden])")

        # ---- admin ----
        page.click('[data-tab="admin"]')
        page.wait_for_selector("#adminUsersBody tr")
        assert "priya@example.com" in page.inner_text("#adminUsersBody") and "ADMIN" in page.inner_text("#adminUsersBody")
        assert page.locator("#adminActivityBody tr").count() >= 3

        # ---- log out, log in with 2FA (TOTP, then backup code) ----
        page.click("#logoutBtn"); page.wait_for_selector("#authWrap:not([hidden])")
        page.fill("#liEmail", "priya@example.com"); page.fill("#liPw", "NewPass123"); page.click("#loginBtn")
        page.wait_for_selector("#totpVerifyForm:not([hidden])")
        page.fill("#tvCode", "123456"); page.click("#tvConfirmBtn"); page.wait_for_selector("#tvCodeErr:not(:empty)")
        page.fill("#tvCode", totp.at(time.time() + 30)); page.click("#tvConfirmBtn")
        page.wait_for_selector("#app:not([hidden])")
        assert page.locator("#tvModeBtn").count() == 0                  # no "use a backup code" option

        # ---- a user who skips 2FA is asked again at every login ----
        page.click("#logoutBtn")
        page.click("#tabRegister")
        page.fill("#rgName", "Sam Skip"); page.fill("#rgEmail", "sam@example.com")
        page.fill("#rgPw", "abc123"); page.fill("#rgPw2", "abc123")          # 6 characters are accepted
        page.click("#registerBtn")
        page.wait_for_selector("#totpSetupForm:not([hidden])")
        page.click("#tsSkipBtn"); page.wait_for_selector("#app:not([hidden])")
        for _ in range(2):
            page.click("#logoutBtn")
            page.fill("#liEmail", "sam@example.com"); page.fill("#liPw", "abc123"); page.click("#loginBtn")
            page.wait_for_selector("#totpSetupForm:not([hidden])")           # asked again
            page.click("#tsSkipBtn"); page.wait_for_selector("#app:not([hidden])")
        page.click("#logoutBtn")
        page.fill("#liEmail", "sam@example.com"); page.fill("#liPw", "abc123"); page.click("#loginBtn")
        page.wait_for_selector("#totpSetupForm:not([hidden])")
        page.click("#tsSkipBtn"); page.wait_for_selector("#app:not([hidden])")      # signed in as Sam for the rest

        # reload keeps the session
        page.reload(); page.wait_for_selector("#app:not([hidden])")

        # ---- forgot password (development mode shows the code on screen) ----
        page.click("#logoutBtn")
        page.click('#loginForm [data-auth="forgot"]')
        page.fill("#fgEmail", "priya@example.com"); page.click("#forgotBtn")
        page.wait_for_selector("#resetForm:not([hidden])")
        code = page.inner_text("#demoMail .code")
        assert len(code) == 6
        page.fill("#rsCode", code); page.fill("#rsPw", "Fresh1234pass"); page.fill("#rsPw2", "Fresh1234pass"); page.click("#resetBtn")
        page.wait_for_selector("#loginOk:not([hidden])")
        page.fill("#liPw", "Fresh1234pass"); page.click("#loginBtn")
        page.wait_for_selector("#totpVerifyForm:not([hidden])")      # 2FA still required after a reset

        # ---- brute force protection is visible in the UI ----
        page.click("#tvCancelBtn")
        for _ in range(6):
            page.fill("#liEmail", "priya@example.com"); page.fill("#liPw", "badpass123"); page.click("#loginBtn")
            expect(page.locator("#loginBtn")).to_be_enabled()
        assert "Too many failed" in page.inner_text("#loginErr")
        browser.close()
    assert errors == [], errors
