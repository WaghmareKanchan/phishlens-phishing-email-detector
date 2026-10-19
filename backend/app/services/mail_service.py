import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

log = logging.getLogger("phishlens.mail")


def send_reset_code(to_addr: str, code: str) -> bool:
    """Send the password-reset code. Returns True only if an e-mail was really handed to SMTP."""
    s = get_settings()
    if not s.smtp_host:
        if not s.is_production:
            log.info("DEV: SMTP not configured. Reset code for %s is %s", to_addr, code)
        else:
            log.warning("SMTP is not configured: password-reset e-mail NOT sent to %s", to_addr)
        return False
    msg = EmailMessage()
    msg["Subject"] = "Your PhishLens password reset code"
    msg["From"] = s.smtp_from
    msg["To"] = to_addr
    msg.set_content(
        f"Your PhishLens reset code is {code}\n\nIt is valid for {s.reset_code_ttl_minutes} minutes. "
        "If you did not ask for it you can ignore this e-mail.")
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001
        log.exception("could not send reset e-mail")
        return False
