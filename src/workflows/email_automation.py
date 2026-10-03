"""Email Automation Workflow Module."""

import email
import imaplib
import json
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from src.config.logging_config import logger
from src.config.settings import settings


@dataclass
class EmailResult:
    """Result of an email operation."""

    success: bool
    message: str
    error: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class EmailMessage:
    """Represents an email message."""

    subject: str
    sender: str
    recipients: list[str]
    body: str
    html_body: str | None = None
    attachments: list[str] | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None

    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []
        if self.cc is None:
            self.cc = []
        if self.bcc is None:
            self.bcc = []


class EmailAutomation:
    """Handles email automation operations."""

    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.email_address = settings.EMAIL_ADDRESS
        self.email_password = settings.EMAIL_PASSWORD
        self._smtp_connection = None

    def _get_smtp_connection(self) -> smtplib.SMTP:
        """Get or create SMTP connection."""
        if self._smtp_connection is None:
            self._smtp_connection = smtplib.SMTP(self.smtp_server, self.smtp_port)
            self._smtp_connection.starttls(context=ssl.create_default_context())
            self._smtp_connection.login(self.email_address, self.email_password)
        return self._smtp_connection

    def _create_message(self, email_msg: EmailMessage) -> MIMEMultipart:
        """Create a MIME message from EmailMessage."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = email_msg.subject
        msg["From"] = self.email_address
        msg["To"] = ", ".join(email_msg.recipients)

        if email_msg.cc:
            msg["Cc"] = ", ".join(email_msg.cc)

        # Add text body
        text_part = MIMEText(email_msg.body, "plain")
        msg.attach(text_part)

        # Add HTML body if provided
        if email_msg.html_body:
            html_part = MIMEText(email_msg.html_body, "html")
            msg.attach(html_part)

        # Add attachments
        for attachment_path in email_msg.attachments or []:
            path = Path(attachment_path)
            if path.exists():
                with open(path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition", f'attachment; filename="{path.name}"'
                )
                msg.attach(part)

        return msg

    def send_email(self, email_msg: EmailMessage) -> EmailResult:
        """Send a single email."""
        try:
            smtp = self._get_smtp_connection()
            msg = self._create_message(email_msg)

            all_recipients = email_msg.recipients + (email_msg.cc or []) + (email_msg.bcc or [])
            smtp.sendmail(self.email_address, all_recipients, msg.as_string())

            logger.info(f"Email sent to {email_msg.recipients}")
            return EmailResult(
                success=True,
                message=f"Email sent successfully to {', '.join(email_msg.recipients)}",
                details={
                    "recipients": email_msg.recipients,
                    "subject": email_msg.subject,
                },
            )

        except smtplib.SMTPAuthenticationError:
            return EmailResult(
                success=False,
                message="",
                error="SMTP authentication failed. Check credentials.",
            )
        except smtplib.SMTPRecipientsRefused as e:
            return EmailResult(
                success=False, message="", error=f"Recipient refused: {e}"
            )
        except smtplib.SMTPException as e:
            return EmailResult(success=False, message="", error=f"SMTP error: {e!s}")
        except Exception as e:
            logger.error(f"Send email error: {e}")
            return EmailResult(success=False, message="", error=str(e))

    def send_bulk_email(
        self, emails: list[EmailMessage], delay: float = 1.0
    ) -> EmailResult:
        """Send multiple emails with optional delay between sends."""
        import time

        results = []
        for email_msg in emails:
            result = self.send_email(email_msg)
            results.append(
                {
                    "recipients": email_msg.recipients,
                    "subject": email_msg.subject,
                    "success": result.success,
                    "error": result.error,
                }
            )
            if delay > 0:
                time.sleep(delay)

        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        return EmailResult(
            success=failed == 0,
            message=f"Bulk email complete: {successful} sent, {failed} failed",
            details={"results": results},
        )

    def read_emails(
        self, folder: str = "INBOX", criteria: str = "ALL", limit: int = 10
    ) -> EmailResult:
        """Read emails from IMAP server."""
        try:
            imap = imaplib.IMAP4_SSL(self.smtp_server.replace("smtp", "imap"))
            imap.login(self.email_address, self.email_password)
            imap.select(folder)

            status, messages = imap.search(None, criteria)
            if status != "OK":
                return EmailResult(
                    success=False, message="", error="Failed to search emails"
                )

            email_ids = messages[0].split()
            email_ids = email_ids[-limit:] if limit else email_ids

            emails = []
            for eid in reversed(email_ids):
                status, msg_data = imap.fetch(eid, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]  # type: ignore[index]
                msg = email.message_from_bytes(raw_email)  # type: ignore[arg-type]

                # Parse email
                subject = msg.get("Subject", "")
                sender = msg.get("From", "")
                date = msg.get("Date", "")

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                body = payload.decode("utf-8", errors="ignore")
                            break
                else:
                    payload = msg.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode("utf-8", errors="ignore")

                emails.append(
                    {
                        "id": eid.decode(),
                        "subject": subject,
                        "sender": sender,
                        "date": date,
                        "body": body[:500] + "..." if len(body) > 500 else body,
                    }
                )

            imap.close()
            imap.logout()

            return EmailResult(
                success=True,
                message=f"Retrieved {len(emails)} emails",
                details={"emails": emails},
            )

        except imaplib.IMAP4.error as e:
            return EmailResult(success=False, message="", error=f"IMAP error: {e!s}")
        except Exception as e:
            logger.error(f"Read emails error: {e}")
            return EmailResult(success=False, message="", error=str(e))

    def create_template(
        self, name: str, subject: str, body: str, html_body: str | None = None
    ) -> EmailResult:
        """Save an email template."""
        try:
            templates_dir = settings.DATA_DIR / "email_templates"
            templates_dir.mkdir(parents=True, exist_ok=True)

            template_file = templates_dir / f"{name}.json"

            template = {
                "name": name,
                "subject": subject,
                "body": body,
                "html_body": html_body,
                "created_at": datetime.now().isoformat(),
            }

            with open(template_file, "w") as f:
                json.dump(template, f, indent=2)

            return EmailResult(
                success=True,
                message=f"Template '{name}' created",
                details={"template": template},
            )

        except Exception as e:
            logger.error(f"Create template error: {e}")
            return EmailResult(success=False, message="", error=str(e))

    def get_template(self, name: str) -> EmailResult:
        """Load an email template."""
        try:
            template_file = settings.DATA_DIR / "email_templates" / f"{name}.json"

            if not template_file.exists():
                return EmailResult(
                    success=False, message="", error=f"Template '{name}' not found"
                )

            with open(template_file) as f:
                template = json.load(f)

            return EmailResult(
                success=True,
                message=f"Template '{name}' loaded",
                details={"template": template},
            )

        except Exception as e:
            logger.error(f"Get template error: {e}")
            return EmailResult(success=False, message="", error=str(e))

    def list_templates(self) -> EmailResult:
        """List all email templates."""
        try:
            templates_dir = settings.DATA_DIR / "email_templates"
            templates_dir.mkdir(parents=True, exist_ok=True)

            templates = []
            for template_file in templates_dir.glob("*.json"):
                with open(template_file) as f:
                    template = json.load(f)
                templates.append(template)

            return EmailResult(
                success=True,
                message=f"Found {len(templates)} templates",
                details={"templates": templates},
            )

        except Exception as e:
            logger.error(f"List templates error: {e}")
            return EmailResult(success=False, message="", error=str(e))

    def close(self):
        """Close SMTP connection."""
        if self._smtp_connection:
            try:
                self._smtp_connection.quit()
            except Exception:
                pass
            self._smtp_connection = None


def create_email_automation() -> EmailAutomation:
    """Factory function to create email automation instance."""
    return EmailAutomation()
