"""
SMTP email sender — pure Python smtplib, no third-party APIs.

Gmail setup (one-time):
  1. Enable 2-Step Verification on your Google account
  2. Google Account → Security → App Passwords → generate one for "Mail"
  3. Copy the 16-char password into SMTP_PASSWORD in backend/.env
     (Never use your real Gmail password here)
"""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from core.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()


def _html_body(name: str, otp: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:32px;margin:0">
  <div style="max-width:460px;margin:0 auto;background:#1e293b;border-radius:12px;
              padding:32px;border:1px solid #334155">
    <div style="text-align:center;margin-bottom:24px">
      <div style="font-size:36px">⚠️</div>
      <h2 style="color:#f1f5f9;margin:8px 0 4px">GeoSentinel</h2>
      <p style="color:#94a3b8;font-size:13px;margin:0">Real-Time Disaster Monitor</p>
    </div>
    <p style="color:#cbd5e1">Hi <strong>{name}</strong>,</p>
    <p style="color:#94a3b8;margin-bottom:20px">
      Your email verification code is:
    </p>
    <div style="text-align:center;margin:28px 0">
      <span style="font-size:44px;font-weight:bold;letter-spacing:10px;
                   color:#38bdf8;background:#0f172a;padding:16px 28px;
                   border-radius:10px;display:inline-block">
        {otp}
      </span>
    </div>
    <p style="color:#94a3b8;font-size:13px;text-align:center">
      This code expires in <strong>10 minutes</strong>.
    </p>
    <hr style="border:1px solid #334155;margin:24px 0">
    <p style="color:#64748b;font-size:12px;text-align:center">
      If you did not register, you can safely ignore this email.
    </p>
  </div>
</body>
</html>"""


def send_otp_email(to_email: str, name: str, otp: str) -> bool:
    """
    Send OTP via SMTP. Returns True on success, False on failure.
    Failure is logged but does NOT raise — callers decide how to handle it.
    """
    user = settings.SMTP_USER
    pwd  = settings.SMTP_PASSWORD
    if not user or not pwd:
        logger.error("[EMAIL] SMTP_USER / SMTP_PASSWORD not set in .env")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "GeoSentinel — Email Verification Code"
    msg["From"]    = f"{settings.SMTP_FROM_NAME} <{user}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(f"Hi {name},\n\nYour code: {otp}\n\nExpires in 10 mins.", "plain"))
    msg.attach(MIMEText(_html_body(name, otp), "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(user, pwd)
            srv.sendmail(user, to_email, msg.as_string())
        logger.info(f"[EMAIL] OTP sent → {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "[EMAIL] SMTP auth failed. For Gmail, use an App Password "
            "(Google Account → Security → App Passwords), NOT your real password."
        )
        return False
    except Exception as exc:
        logger.error(f"[EMAIL] Failed to send to {to_email}: {exc}")
        return False