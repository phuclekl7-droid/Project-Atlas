"""
Gmail / Email Sender Plugin (Feature #30).
Sends emails via SMTP using Python's built-in smtplib.

Supports:
- Plain text and HTML emails
- Gmail SMTP (requires App Password)
- Custom SMTP servers
- Multiple recipients

Usage:
    EmailSenderPlugin.execute("to:user@example.com subject:Hello body:This is a test")
    EmailSenderPlugin.execute("send to:user@example.com -- tôi muốn gửi email thông báo")
"""

import os
import smtplib
import re
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("email_sender")


@dataclass
class EmailConfig:
    """SMTP server configuration."""
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True


@dataclass
class EmailMessage:
    """Parsed email message components."""
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    is_html: bool = False


def _parse_email_input(input_str: str) -> Optional[EmailMessage]:
    """
    Parse user input into email components.

    Supported formats:
        "to:user@example.com subject:Hello body:This is a test"
        "to:a@b.com, c@d.com subject:Meeting body:Let's meet"
        "cc:e@f.com subject:Draft body:Check this"
    """
    msg = EmailMessage()

    # Extract components using regex
    to_match = re.search(r'\bto:\s*(.+?)(?:\s+(?:cc|bcc|subject|body):|\s*$)', input_str, re.DOTALL)
    cc_match = re.search(r'\bcc:\s*(.+?)(?:\s+(?:to|bcc|subject|body):|\s*$)', input_str, re.DOTALL)
    bcc_match = re.search(r'\bbcc:\s*(.+?)(?:\s+(?:to|cc|subject|body):|\s*$)', input_str, re.DOTALL)
    subject_match = re.search(r'\bsubject:\s*(.+?)(?:\s+(?:to|cc|bcc|body):|\s*$)', input_str, re.DOTALL)
    body_match = re.search(r'\bbody:\s*(.+)$', input_str, re.DOTALL)

    if to_match:
        msg.to = [addr.strip() for addr in to_match.group(1).split(",") if addr.strip()]
    if cc_match:
        msg.cc = [addr.strip() for addr in cc_match.group(1).split(",") if addr.strip()]
    if bcc_match:
        msg.bcc = [addr.strip() for addr in bcc_match.group(1).split(",") if addr.strip()]
    if subject_match:
        msg.subject = subject_match.group(1).strip()
    if body_match:
        msg.body = body_match.group(1).strip()

    # Check for HTML marker
    if "<html" in msg.body.lower() or "<h1" in msg.body.lower() or "<p>" in msg.body:
        msg.is_html = True

    return msg if msg.to else None


def _send_email(config: EmailConfig, msg: EmailMessage) -> Optional[str]:
    """
    Send email via SMTP.

    Args:
        config: SMTP server configuration
        msg: Email message components

    Returns:
        Error string if failed, None if successful
    """
    try:
        # Build message
        mime_msg = MIMEMultipart("alternative")
        mime_msg["From"] = config.username
        mime_msg["To"] = ", ".join(msg.to)
        if msg.cc:
            mime_msg["Cc"] = ", ".join(msg.cc)
        mime_msg["Subject"] = msg.subject

        # Attach body
        if msg.is_html:
            mime_msg.attach(MIMEText(msg.body, "html"))
        else:
            mime_msg.attach(MIMEText(msg.body, "plain", "utf-8"))

        # All recipients for SMTP
        all_recipients = msg.to + msg.cc + msg.bcc

        # Connect and send
        with smtplib.SMTP(config.host, config.port, timeout=30) as server:
            if config.use_tls:
                server.starttls()
            if config.username and config.password:
                server.login(config.username, config.password)
            server.sendmail(config.username, all_recipients, mime_msg.as_string())

        logger.info(f"Email sent to {', '.join(msg.to)}, subject='{msg.subject}'")
        return None

    except smtplib.SMTPAuthenticationError:
        return (
            "❌ SMTP authentication failed.\n\n"
            "Nếu dùng Gmail, bạn cần tạo **App Password**:\n"
            "1. Vào https://myaccount.google.com/apppasswords\n"
            "2. Chọn 'Mail' và tạo mật khẩu\n"
            "3. Đặt mật khẩu đó vào biến môi trường EMAIL_PASSWORD"
        )
    except smtplib.SMTPException as e:
        return f"❌ SMTP error: {e}"
    except Exception as e:
        return f"❌ Failed to send email: {e}"


class EmailSenderPlugin(BasePlugin):
    """
    Sends emails via SMTP.

    Reads SMTP config from environment variables:
    - EMAIL_HOST (default: smtp.gmail.com)
    - EMAIL_PORT (default: 587)
    - EMAIL_USERNAME (required)
    - EMAIL_PASSWORD (required)
    - EMAIL_USE_TLS (default: true)

    Examples:
        "to:user@gmail.com subject:Hello body:This is a test message"
        "to:a@b.com, c@d.com cc:admin@b.com subject:Report body:See attachment"
    """

    name = "email_sender"
    description = "Gửi email qua SMTP (Gmail, Outlook, custom server)"

    def _load_config(self) -> EmailConfig:
        """Load SMTP config from environment variables."""
        return EmailConfig(
            host=os.environ.get("EMAIL_HOST", "smtp.gmail.com"),
            port=int(os.environ.get("EMAIL_PORT", "587")),
            username=os.environ.get("EMAIL_USERNAME", ""),
            password=os.environ.get("EMAIL_PASSWORD", ""),
            use_tls=os.environ.get("EMAIL_USE_TLS", "true").lower() == "true",
        )

    def execute(self, input_str: str) -> PluginResult:
        """Parse and send an email."""
        if not input_str.strip():
            return PluginResult(
                success=False,
                error="Vui lòng nhập thông tin email.\n\n"
                      "Định dạng: `to:email@example.com subject:Tiêu đề body:Nội dung`"
            )

        parsed = _parse_email_input(input_str)
        if not parsed or not parsed.to:
            return PluginResult(
                success=False,
                error="Không tìm thấy địa chỉ người nhận.\n\n"
                      "Đảm bảo có `to:` trong tin nhắn.\n"
                      "Ví dụ: `to:user@example.com subject:Hello body:Test`"
            )

        if not parsed.subject:
            return PluginResult(
                success=False,
                error="Thiếu tiêu đề email. Thêm `subject:` vào tin nhắn."
            )

        if not parsed.body:
            return PluginResult(
                success=False,
                error="Thiếu nội dung email. Thêm `body:` vào tin nhắn."
            )

        config = self._load_config()
        if not config.username:
            return PluginResult(
                success=False,
                error=(
                    "❌ Chưa cấu hình email.\n\n"
                    "Vui lòng đặt các biến môi trường:\n"
                    "- `EMAIL_USERNAME`: địa chỉ email của bạn\n"
                    "- `EMAIL_PASSWORD`: mật khẩu ứng dụng\n\n"
                    "Với Gmail, dùng App Password: "
                    "https://myaccount.google.com/apppasswords"
                )
            )

        error = _send_email(config, parsed)
        if error:
            return PluginResult(success=False, error=error)

        # Build success message
        lines = [
            f"✅ **Email sent successfully!**",
            f"",
            f"- **To:** {', '.join(parsed.to)}",
            f"- **Subject:** {parsed.subject}",
        ]
        if parsed.cc:
            lines.append(f"- **CC:** {', '.join(parsed.cc)}")
        lines.append(f"- **SMTP:** {config.host}:{config.port}")

        return PluginResult(success=True, output="\n".join(lines))
