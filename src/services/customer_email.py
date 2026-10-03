"""Enhanced Customer Email Service for intelligent workflows."""

import email
import imaplib
import json
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

from openai import OpenAI

from src.config.logging_config import logger
from src.config.settings import settings
from src.db import db_service
from src.db.models import Customer, EmailLog
from src.services.approval import create_approval_service


class EmailStatus(Enum):
    """Email status enumeration."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"


class EmailTemplateType(Enum):
    """Predefined email template types."""
    WELCOME = "welcome"
    FOLLOW_UP = "follow_up"
    RE_ENGAGEMENT = "re_engagement"
    PAYMENT_REMINDER = "payment_reminder"
    SUPPORT_FOLLOWUP = "support_followup"
    HIGH_VALUE_CHECKIN = "high_value_checkin"
    CUSTOM = "custom"


@dataclass
class EmailDraft:
    """Email draft before approval."""
    customer_id: Optional[int]
    customer_email: str
    customer_name: str
    subject: str
    body: str
    html_body: Optional[str] = None
    template_type: EmailTemplateType = EmailTemplateType.CUSTOM
    template_name: Optional[str] = None
    metadata: Optional[dict] = None


@dataclass
class EmailResult:
    """Result of an email operation."""
    success: bool
    message: str
    error: Optional[str] = None
    details: Optional[dict] = None
    email_id: Optional[int] = None


class CustomerEmailService:
    """Enhanced email service for customer workflows with personalization and approval."""
    
    # Built-in templates
    BUILTIN_TEMPLATES = {
        EmailTemplateType.WELCOME: {
            "subject": "Welcome to {{company_name}}, {{customer_name}}!",
            "body": """Dear {{customer_name}},

Welcome to {{company_name}}! We're thrilled to have you on board.

{{#if company}}
We know {{company}} will benefit greatly from our services.
{{/if}}

Here's what you can expect from us:
• Dedicated support team
• Regular updates and improvements
• Personalized recommendations based on your needs

If you have any questions, don't hesitate to reach out to our support team at {{support_email}}.

Best regards,
The {{company_name}} Team
""",
        },
        EmailTemplateType.FOLLOW_UP: {
            "subject": "Following up: {{subject_line}}",
            "body": """Hi {{customer_name}},

I wanted to follow up on our previous conversation about {{topic}}.

{{#if last_interaction}}
As discussed on {{last_interaction}}, we wanted to ensure everything is progressing smoothly.
{{/if}}

Please let me know if you have any questions or if there's anything else I can help with.

Best regards,
{{sender_name}}
{{sender_title}}
{{company_name}}
""",
        },
        EmailTemplateType.RE_ENGAGEMENT: {
            "subject": "We miss you, {{customer_name}}!",
            "body": """Hi {{customer_name}},

We noticed it's been a while since we last connected. We value your relationship with {{company_name}} and want to make sure we're meeting your needs.

{{#if last_purchase}}
Since your last purchase on {{last_purchase}}, we've introduced some exciting new features:
• Feature 1: Description
• Feature 2: Description
• Feature 3: Description
{{/if}}

As a token of our appreciation, we'd like to offer you {{special_offer}}.

We'd love to hear from you and see how we can help.

Best regards,
The {{company_name}} Team
""",
        },
        EmailTemplateType.PAYMENT_REMINDER: {
            "subject": "Payment Reminder: Invoice #{{invoice_number}} - ${{amount_due}}",
            "body": """Dear {{customer_name}},

This is a friendly reminder that payment for invoice #{{invoice_number}} for ${{amount_due}} is due on {{due_date}}.

{{#if overdue_days}}
This payment is {{overdue_days}} days overdue. Please process this as soon as possible to avoid any service interruptions.
{{/if}}

You can make a payment through:
• Online portal: {{payment_portal}}
• Bank transfer (details attached)
• Contact our billing team at {{billing_email}}

If you've already made this payment, please disregard this notice.

Thank you for your prompt attention to this matter.

Best regards,
{{company_name}} Billing Department
""",
        },
        EmailTemplateType.SUPPORT_FOLLOWUP: {
            "subject": "Follow-up on your support request #{{ticket_number}}",
            "body": """Hi {{customer_name}},

I'm following up on your support request #{{ticket_number}} regarding "{{ticket_subject}}".

{{#if status}}
Current status: {{status}}
{{/if}}

{{#if resolution}}
Resolution: {{resolution}}
{{/if}}

Is there anything else you need assistance with? Please don't hesitate to reach out if the issue persists or if you have additional questions.

Best regards,
{{support_agent_name}}
{{company_name}} Support Team
""",
        },
        EmailTemplateType.HIGH_VALUE_CHECKIN: {
            "subject": "Checking in with you, {{customer_name}}",
            "body": """Dear {{customer_name}},

As one of our valued {{segment}} customers, I wanted to personally check in and see how things are going with {{company}}.

{{#if recent_purchase}}
We noticed your recent investment in {{recent_purchase}} - we hope it's delivering great value!
{{/if}}

Your feedback is incredibly important to us. Is there anything we can do to better support your goals? We're always looking for ways to improve your experience.

I'd love to schedule a brief call at your convenience to discuss how we can continue to add value.

Best regards,
{{account_manager_name}}
{{account_manager_title}}
{{company_name}}
""",
        },
    }
    
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.email_address = settings.EMAIL_ADDRESS
        self.email_password = settings.EMAIL_PASSWORD
        self._smtp_connection = None
        self._llm_client: Optional[OpenAI] = None
    
    def _get_session(self):
        """Get a fresh database session."""
        return db_service.get_session()
    
    def _execute_in_transaction(self, func):
        """Execute a function within a database transaction."""
        session = db_service.get_session()
        try:
            result = func(session)
            session.commit()
            # Only refresh/expunge SQLAlchemy model instances
            if result is not None and hasattr(result, '__table__'):
                session.refresh(result)
                session.expunge(result)
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def _get_llm_client(self) -> OpenAI:
        """Get or create LLM client."""
        if self._llm_client is None:
            llm_config = settings.get_llm_config()
            self._llm_client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"],
            )
        return self._llm_client
    
    def _get_smtp_connection(self) -> smtplib.SMTP:
        """Get or create SMTP connection."""
        if self._smtp_connection is None:
            self._smtp_connection = smtplib.SMTP(self.smtp_server, self.smtp_port)
            self._smtp_connection.starttls(context=ssl.create_default_context())
            self._smtp_connection.login(self.email_address, self.email_password)
        return self._smtp_connection
    
    def _create_message(self, email_msg: EmailDraft, from_email: Optional[str] = None) -> MIMEMultipart:
        """Create a MIME message from EmailDraft."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = email_msg.subject
        msg["From"] = from_email or self.email_address
        msg["To"] = email_msg.customer_email
        
        # Add text body
        text_part = MIMEText(email_msg.body, "plain")
        msg.attach(text_part)
        
        # Add HTML body if provided
        if email_msg.html_body:
            html_part = MIMEText(email_msg.html_body, "html")
            msg.attach(html_part)
        
        return msg
    
    def _render_template(self, template: str, context: dict) -> str:
        """Simple template rendering with {{variable}} and {{#if variable}} support."""
        # Handle {{#if variable}}...{{/if}} blocks
        def replace_if(match):
            var_name = match.group(1)
            content = match.group(2)
            if context.get(var_name):
                return content
            return ""
        
        template = re.sub(r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}', replace_if, template, flags=re.DOTALL)
        
        # Handle {{variable}} replacements
        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", str(value) if value else "")
        
        return template
    
    def _build_customer_context(self, customer: Customer) -> dict:
        """Build context dictionary from customer data."""
        return {
            "customer_name": customer.name or "Valued Customer",
            "customer_email": customer.email or "",
            "company": customer.company or "",
            "customer_type": customer.customer_type.value,
            "customer_segment": customer.customer_segment.value if customer.customer_segment else "unknown",
            "total_purchase_value": f"${customer.total_purchase_value:,.2f}",
            "order_count": customer.order_count,
            "payment_status": customer.payment_status.value,
            "outstanding_amount": f"${customer.outstanding_amount:,.2f}",
            "support_status": customer.support_status.value,
            "last_contact_date": customer.last_contact_date.strftime("%Y-%m-%d") if customer.last_contact_date else "Never",
            "last_purchase_date": customer.last_purchase_date.strftime("%Y-%m-%d") if customer.last_purchase_date else "Never",
            "signup_date": customer.signup_date.strftime("%Y-%m-%d") if customer.signup_date else "Unknown",
            "priority": customer.priority,
            "notes": customer.notes or "",
            # Company defaults
            "company_name": "Our Company",
            "support_email": "support@company.com",
            "billing_email": "billing@company.com",
            "payment_portal": "https://payments.company.com",
            "sender_name": "Account Manager",
            "sender_title": "Customer Success",
            "account_manager_name": "Account Manager",
            "account_manager_title": "Customer Success",
        }
    
    def generate_email(
        self,
        customer: Customer,
        template_type: EmailTemplateType = EmailTemplateType.CUSTOM,
        custom_subject: Optional[str] = None,
        custom_body: Optional[str] = None,
        custom_html: Optional[str] = None,
        tone: str = "professional",
        additional_context: Optional[dict] = None,
    ) -> EmailDraft:
        """Generate a personalized email for a customer."""
        
        if not customer.email:
            raise ValueError(f"Customer {customer.customer_id} has no email address")
        
        context = self._build_customer_context(customer)
        if additional_context:
            context.update(additional_context)
        
        if template_type != EmailTemplateType.CUSTOM and template_type in self.BUILTIN_TEMPLATES:
            # Use built-in template
            template = self.BUILTIN_TEMPLATES[template_type]
            subject = self._render_template(template["subject"], context)
            body = self._render_template(template["body"], context)
            html_body = None  # Could generate HTML version
        else:
            # Custom template - use AI for personalization if not provided
            if custom_subject and custom_body:
                subject = self._render_template(custom_subject, context)
                body = self._render_template(custom_body, context)
                html_body = self._render_template(custom_html, context) if custom_html else None
            else:
                # Use AI to generate personalized email
                subject, body, html_body = self._generate_with_ai(customer, context, tone)
        
        return EmailDraft(
            customer_id=customer.id,
            customer_email=customer.email,
            customer_name=customer.name,
            subject=subject,
            body=body,
            html_body=html_body,
            template_type=template_type,
            metadata=context,
        )
    
    def _generate_with_ai(self, customer: Customer, context: dict, tone: str) -> tuple[str, str, Optional[str]]:
        """Use AI to generate personalized email."""
        try:
            client = self._get_llm_client()
            
            system_prompt = f"""You are a professional customer communications specialist. Generate a personalized email for the customer below.

Tone: {tone}

Customer Profile:
{json.dumps(context, indent=2)}

Generate a JSON response with:
- subject: Email subject line
- body: Plain text email body
- html_body: HTML version of the email (optional)

Do not invent customer information. If information is missing, write around it naturally.
Always be professional and respectful."""
            
            response = client.chat.completions.create(
                model=settings.get_llm_config()["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the personalized email."},
                ],
                temperature=0.4,
                response_format={"type": "json_object"},
                max_tokens=1500,
            )
            
            email_data = json.loads(response.choices[0].message.content or "{}")
            return (
                email_data.get("subject", ""),
                email_data.get("body", ""),
                email_data.get("html_body"),
            )
        except Exception as e:
            logger.error(f"AI email generation failed: {e}")
            # Fallback to simple template
            return (
                f"Hello {context.get('customer_name', 'Valued Customer')}",
                f"Dear {context.get('customer_name', 'Valued Customer')},\n\nWe wanted to reach out and connect with you.\n\nBest regards,\nThe Team",
                None,
            )
    
    def validate_email(self, email_address: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email_address))
    
    def send_email_with_approval(
        self,
        draft: EmailDraft,
        approval_id: Optional[int] = None,
        auto_approve: bool = False,
    ) -> EmailResult:
        """Send email with approval workflow integration."""
        from src.db.models import ApprovalStatus
        
        return self._execute_in_transaction(lambda session: self._send_email_with_approval_in_session(
            session, draft, approval_id, auto_approve
        ))
    
    def _send_email_with_approval_in_session(
        self,
        session,
        draft: EmailDraft,
        approval_id: Optional[int] = None,
        auto_approve: bool = False,
    ) -> EmailResult:
        from src.db.models import ApprovalStatus
        from src.services.approval import create_approval_service
        from src.db.repositories import CustomerRepository
        
        approval_service = create_approval_service()
        
        # Validate email
        if not self.validate_email(draft.customer_email):
            return EmailResult(
                success=False,
                message="",
                error=f"Invalid email address: {draft.customer_email}",
            )
        
        # Check if we have an existing approval
        if approval_id:
            approval = approval_service.get_approval(approval_id)
            if not approval:
                return EmailResult(
                    success=False,
                    message="",
                    error=f"Approval {approval_id} not found",
                )
            
            if approval.status != ApprovalStatus.APPROVED:
                return EmailResult(
                    success=False,
                    message="",
                    error=f"Approval not granted: {approval.status.value}",
                )
            
            # Approved - send email
            return self._send_email_in_session(session, draft)
        
        # Check if auto_approve is requested
        if auto_approve:
            return self._send_email_in_session(session, draft)
        
        # Request approval
        approval_service = create_approval_service()
        approval = approval_service.create_approval(
            approval_type="send_email",
            title=f"Send email to {draft.customer_name}",
            description=f"Request to send email '{draft.subject}' to {draft.customer_email}",
            content={"draft": {
                "customer_id": draft.customer_id,
                "customer_email": draft.customer_email,
                "customer_name": draft.customer_name,
                "subject": draft.subject,
                "body": draft.body,
                "html_body": draft.html_body,
            }},
            customer_id=draft.customer_id,
            requested_by="system",
        )
        
        return EmailResult(
            success=True,
            data={
                "approval_id": approval.id,
                "status": "pending_approval",
                "message": f"Approval requested for email to {draft.customer_email}",
            },
        )
    
    def _send_email_in_session(self, session, draft: EmailDraft) -> EmailResult:
        """Actually send the email within a session."""
        try:
            smtp = self._get_smtp_connection()
            msg = self._create_message(draft)
            
            smtp.sendmail(self.email_address, [draft.customer_email], msg.as_string())
            
            logger.info(f"Email sent to {draft.customer_email}")
            
            # Log the sent email
            email_log = EmailLog(
                customer_id=draft.customer_id,
                subject=draft.subject,
                recipients=[draft.customer_email],
                body=draft.body,
                html_body=draft.html_body,
                status=EmailStatus.SENT.value,
                sent_at=datetime.now(),
            )
            session.add(email_log)
            session.commit()
            email_id = email_log.id
            
            return EmailResult(
                success=True,
                message=f"Email sent successfully to {draft.customer_email}",
                email_id=email_id,
                details={
                    "recipient": draft.customer_email,
                    "subject": draft.subject,
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
    
    def send_bulk_emails(
        self,
        drafts: list[EmailDraft],
        delay: float = 1.0,
        require_approval: bool = True,
    ) -> EmailResult:
        """Send multiple emails with approval protection."""
        if not drafts:
            return EmailResult(success=False, message="", error="No emails to send")
        
        # Validate all emails first
        for draft in drafts:
            if not self.validate_email(draft.customer_email):
                return EmailResult(
                    success=False,
                    message="",
                    error=f"Invalid email address: {draft.customer_email}",
                )
        
        # Check for duplicates
        emails_seen = set()
        for draft in drafts:
            if draft.customer_email in emails_seen:
                return EmailResult(
                    success=False,
                    message="",
                    error=f"Duplicate email address detected: {draft.customer_email}",
                )
            emails_seen.add(draft.customer_email)
        
        if require_approval:
            # Request bulk approval
            from src.db import get_db
            from src.services.approval import create_approval_service
            
            db = next(get_db())
            approval_service = create_approval_service(db)
            
            approval = approval_service.create_approval(
                approval_type="bulk_email",
                title=f"Send bulk email to {len(drafts)} recipients",
                description=f"Request to send {len(drafts)} emails to customers",
                content={
                    "drafts": [
                        {
                            "customer_id": d.customer_id,
                            "customer_email": d.customer_email,
                            "customer_name": d.customer_name,
                            "subject": d.subject,
                        }
                        for d in drafts
                    ],
                },
                requested_by="system",
            )
            
            return EmailResult(
                success=True,
                data={
                    "approval_id": approval.id,
                    "status": "pending_approval",
                    "recipient_count": len(drafts),
                    "message": f"Approval requested for {len(drafts)} emails",
                },
            )
        
        # No approval required - send all
        results = []
        for draft in drafts:
            result = self._send_email(draft)
            results.append({
                "customer_id": draft.customer_id,
                "customer_email": draft.customer_email,
                "subject": draft.subject,
                "success": result.success,
                "error": result.error,
            })
        
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        return EmailResult(
            success=failed == 0,
            message=f"Bulk email complete: {successful} sent, {failed} failed",
            details={"results": results},
        )
    
    def get_email_logs(
        self,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[EmailLog]:
        """Get email logs with optional filters."""
        return self._execute_in_transaction(lambda session: self._get_email_logs_in_session(
            session, customer_id, status, limit
        ))
    
    def _get_email_logs_in_session(self, session, customer_id, status, limit):
        query = session.query(EmailLog)
        
        if customer_id:
            query = query.filter(EmailLog.customer_id == customer_id)
        if status:
            query = query.filter(EmailLog.status == status)
        
        return query.order_by(EmailLog.created_at.desc()).limit(limit).all()
    
    def close(self):
        """Close SMTP connection."""
        if self._smtp_connection:
            try:
                self._smtp_connection.quit()
            except Exception:
                pass
            self._smtp_connection = None


def create_customer_email_service() -> CustomerEmailService:
    """Factory function to create customer email service."""
    return CustomerEmailService()
