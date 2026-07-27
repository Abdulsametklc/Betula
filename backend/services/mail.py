"""Transactional email via SMTP (optional in DEBUG)."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from backend.config import get_settings

logger = logging.getLogger("betula.mail")


def smtp_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from)


def send_email(*, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    settings = get_settings()
    if not smtp_configured():
        if settings.debug:
            logger.warning(
                "SMTP yok (DEBUG). Mail gonderilmedi. to=%s subject=%s\n%s",
                to,
                subject,
                text_body,
            )
            return
        raise RuntimeError(
            "E-posta gonderimi yapilandirilmadi. SMTP_HOST ve SMTP_FROM ayarlayin."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    if settings.smtp_ssl:
        with smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, context=context, timeout=30
        ) as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_tls:
                server.starttls(context=context)
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)


def send_activation_code(
    *,
    to: str,
    purpose: str,
    code: str,
    reset_url: str | None = None,
) -> None:
    if purpose == "email_change":
        action = "e-posta değişikliği"
    elif purpose == "password_change":
        action = "şifre değişikliği"
    elif purpose == "password_reset":
        action = "şifre sıfırlama"
    else:
        action = "güvenlik doğrulaması"

    ttl = get_settings().security_code_ttl_minutes
    subject = f"Betula aktivasyon kodu ({action})"

    link_text = ""
    link_html = ""
    if purpose == "password_reset" and reset_url:
        link_text = f"\nŞifre sıfırlama sayfası: {reset_url}\n"
        link_html = (
            f'<p style="margin-top:16px"><a href="{reset_url}" '
            f'style="color:#c2652a;font-weight:600">Şifre sıfırlama sayfasını aç</a></p>'
        )

    text = (
        f"Betula hesabın için {action} aktivasyon kodun: {code}\n"
        f"{link_text}\n"
        f"Bu kod {ttl} dakika geçerlidir.\n"
        f"İşlemi sen başlatmadıysan bu mesajı yok say."
    )
    html = f"""
    <div style="font-family:Manrope,Segoe UI,sans-serif;color:#231a14;line-height:1.5">
      <p>Betula hesabın için <strong>{action}</strong> aktivasyon kodun:</p>
      <p style="font-size:28px;letter-spacing:0.35em;font-weight:700;color:#c2652a">{code}</p>
      {link_html}
      <p style="color:#52443c;font-size:14px">Kod {ttl} dakika geçerlidir.
      Bu işlemi sen başlatmadıysan mesajı yok say.</p>
    </div>
    """
    send_email(to=to, subject=subject, text_body=text, html_body=html)
