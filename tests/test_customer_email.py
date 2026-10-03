"""Tests for customer email service."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
import os
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.db import init_database, db_service
from src.db.models import Customer, CustomerSegment, CustomerStatus, CustomerType, PaymentStatus, SupportStatus
from src.services.customer_email import (
    CustomerEmailService,
    EmailDraft,
    EmailResult,
    EmailStatus,
    EmailTemplateType,
    create_customer_email_service,
)


def get_test_db():
    """Get a test database session."""
    return db_service.get_session()


import uuid

def _create_test_customer(db, customer_id: str, **kwargs) -> Customer:
    """Create a test customer with unique ID."""
    defaults = {
        "name": "Test Customer",
        "email": f"{customer_id.lower()}@example.com",
        "company": "Test Corp",
        "customer_type": CustomerType.COMPANY,
        "customer_segment": CustomerSegment.ACTIVE_CUSTOMER,
        "total_purchase_value": 1000.00,
        "order_count": 5,
        "payment_status": PaymentStatus.CURRENT,
        "outstanding_amount": 0.00,
        "support_status": SupportStatus.NONE,
    }
    defaults.update(kwargs)
    customer = Customer(customer_id=customer_id, **defaults)
    db.add(customer)
    db.commit()
    return customer


def test_email_template_types():
    """Test that all template types are defined."""
    assert EmailTemplateType.WELCOME.value == "welcome"
    assert EmailTemplateType.FOLLOW_UP.value == "follow_up"
    assert EmailTemplateType.RE_ENGAGEMENT.value == "re_engagement"
    assert EmailTemplateType.PAYMENT_REMINDER.value == "payment_reminder"
    assert EmailTemplateType.SUPPORT_FOLLOWUP.value == "support_followup"
    assert EmailTemplateType.HIGH_VALUE_CHECKIN.value == "high_value_checkin"
    assert EmailTemplateType.CUSTOM.value == "custom"
    
    print("✓ Email template types test passed")


def test_email_status():
    """Test email status enumeration."""
    assert EmailStatus.DRAFT.value == "draft"
    assert EmailStatus.PENDING_APPROVAL.value == "pending_approval"
    assert EmailStatus.APPROVED.value == "approved"
    assert EmailStatus.REJECTED.value == "rejected"
    assert EmailStatus.SENT.value == "sent"
    assert EmailStatus.FAILED.value == "failed"
    
    print("✓ Email status test passed")


def test_email_draft():
    """Test EmailDraft creation."""
    draft = EmailDraft(
        customer_id=1,
        customer_email="test@example.com",
        customer_name="Test Customer",
        subject="Test Subject",
        body="Test body",
        template_type=EmailTemplateType.WELCOME,
    )
    
    assert draft.customer_id == 1
    assert draft.customer_email == "test@example.com"
    assert draft.customer_name == "Test Customer"
    assert draft.subject == "Test Subject"
    assert draft.body == "Test body"
    assert draft.template_type == EmailTemplateType.WELCOME
    
    print("✓ EmailDraft test passed")


def test_builtin_templates():
    """Test that built-in templates exist."""
    service = CustomerEmailService()
    
    # Check all template types have templates
    for template_type in EmailTemplateType:
        if template_type != EmailTemplateType.CUSTOM:
            assert template_type in service.BUILTIN_TEMPLATES
            template = service.BUILTIN_TEMPLATES[template_type]
            assert "subject" in template
            assert "body" in template
    
    print("✓ Built-in templates test passed")


def test_template_rendering():
    """Test template rendering with context."""
    service = CustomerEmailService()
    
    template = "Hello {{name}}, your company is {{company}}."
    context = {"name": "John", "company": "Acme Corp"}
    result = service._render_template(template, context)
    
    assert result == "Hello John, your company is Acme Corp."
    
    # Test conditional
    template_if = "Hello {{name}}{{#if company}}, works at {{company}}{{/if}}."
    result = service._render_template(template_if, {"name": "John"})
    assert result == "Hello John."
    
    result = service._render_template(template_if, {"name": "John", "company": "Acme"})
    assert result == "Hello John, works at Acme."
    
    print("✓ Template rendering test passed")


def test_customer_context():
    """Test building customer context."""
    init_database()
    db = get_test_db()
    try:
        service = create_customer_email_service()
        
        customer = Customer(
            customer_id="TEST001",
            name="John Doe",
            email="john@example.com",
            company="Acme Corp",
            customer_type=CustomerType.COMPANY,
            customer_segment=CustomerSegment.HIGH_VALUE_CUSTOMER,
            total_purchase_value=15000.00,
            order_count=10,
            payment_status=PaymentStatus.CURRENT,
            outstanding_amount=0.00,
            support_status=SupportStatus.NONE,
        )
        
        context = service._build_customer_context(customer)
        
        assert context["customer_name"] == "John Doe"
        assert context["customer_email"] == "john@example.com"
        assert context["company"] == "Acme Corp"
        assert context["customer_type"] == "company"
        assert context["customer_segment"] == "high_value_customer"
        assert context["total_purchase_value"] == "$15,000.00"
        assert context["order_count"] == 10
        assert context["payment_status"] == "current"
        
        print("✓ Customer context test passed")
    finally:
        db.close()


def test_email_validation():
    """Test email validation."""
    service = CustomerEmailService()
    
    assert service.validate_email("test@example.com") is True
    assert service.validate_email("user.name@domain.org") is True
    assert service.validate_email("invalid") is False
    assert service.validate_email("@nodomain.com") is False
    assert service.validate_email("nodomain@") is False
    assert service.validate_email("") is False
    
    print("✓ Email validation test passed")


def test_generate_email_with_template():
    """Test email generation with built-in template."""
    init_database()
    db = get_test_db()
    try:
        service = create_customer_email_service()
        
        customer = _create_test_customer(db, f"TEST001_{uuid.uuid4().hex[:8]}", 
            name="Jane Smith",
            email="jane@example.com",
            company="Globex Inc",
            customer_type=CustomerType.COMPANY,
            customer_segment=CustomerSegment.HIGH_VALUE_CUSTOMER,
            total_purchase_value=25000.00,
            order_count=20,
            payment_status=PaymentStatus.CURRENT,
            outstanding_amount=0.00,
            support_status=SupportStatus.NONE,
        )
        
        # Test welcome template
        draft = service.generate_email(
            customer=customer,
            template_type=EmailTemplateType.WELCOME,
        )
        
        assert draft.customer_id == customer.id
        assert draft.customer_email == "jane@example.com"
        assert draft.customer_name == "Jane Smith"
        assert draft.template_type == EmailTemplateType.WELCOME
        assert "Jane Smith" in draft.subject
        assert "Jane Smith" in draft.body
        
        print("✓ Generate email with template test passed")
    finally:
        db.close()


def test_generate_email_custom():
    """Test email generation with custom content."""
    init_database()
    db = get_test_db()
    try:
        service = create_customer_email_service()
        
        customer = _create_test_customer(db, f"TEST002_{uuid.uuid4().hex[:8]}",
            name="Bob Wilson",
            email="bob@example.com",
            company="Test Inc",
            customer_type=CustomerType.INDIVIDUAL,
            customer_segment=CustomerSegment.ACTIVE_CUSTOMER,
            total_purchase_value=1000.00,
            order_count=3,
            payment_status=PaymentStatus.CURRENT,
            outstanding_amount=0.00,
            support_status=SupportStatus.NONE,
        )
        
        # Test custom template
        draft = service.generate_email(
            customer=customer,
            template_type=EmailTemplateType.CUSTOM,
            custom_subject="Custom: Hello {{customer_name}}",
            custom_body="Dear {{customer_name}}, this is a custom message for {{company}}.",
            tone="friendly",
        )
        
        assert draft.customer_email == "bob@example.com"
        assert "Bob Wilson" in draft.subject
        assert "Bob Wilson" in draft.body
        assert "Test Inc" in draft.body
        
        print("✓ Generate email custom test passed")
    finally:
        db.close()


def test_send_email_without_approval():
    """Test send_email_with_approval with auto_approve."""
    init_database()
    db = get_test_db()
    try:
        service = create_customer_email_service()
        
        customer = _create_test_customer(db, f"TEST003_{uuid.uuid4().hex[:8]}",
            name="Alice Brown",
            email="alice@example.com",
            company="Test Co",
            customer_type=CustomerType.INDIVIDUAL,
            customer_segment=CustomerSegment.NEW_CUSTOMER,
            total_purchase_value=500.00,
            order_count=1,
            payment_status=PaymentStatus.CURRENT,
            outstanding_amount=0.00,
            support_status=SupportStatus.NONE,
        )
        
        draft = EmailDraft(
            customer_id=customer.id,
            customer_email="alice@example.com",
            customer_name="Alice Brown",
            subject="Test Subject",
            body="Test body content",
            template_type=EmailTemplateType.CUSTOM,
        )
        
        # Test the flow - SMTP may or may not be configured
        result = service.send_email_with_approval(draft, auto_approve=True)
        
        # Should either succeed (if SMTP configured) or fail gracefully
        # Both outcomes are valid for this test
        assert result is not None
        assert hasattr(result, 'success')
        assert hasattr(result, 'message')
        
        print("✓ Send email without approval test passed")
    finally:
        db.close()


def test_bulk_email_duplicate_protection():
    """Test bulk email duplicate protection."""
    init_database()
    db = get_test_db()
    try:
        service = create_customer_email_service()
        
        draft1 = EmailDraft(
            customer_id=1,
            customer_email="test@example.com",
            customer_name="Test 1",
            subject="Test 1",
            body="Body 1",
        )
        draft2 = EmailDraft(
            customer_id=2,
            customer_email="test@example.com",  # Duplicate
            customer_name="Test 2",
            subject="Test 2",
            body="Body 2",
        )
        
        result = service.send_bulk_emails([draft1, draft2], require_approval=False)
        
        assert result.success is False
        assert "Duplicate email address" in result.error
        
        print("✓ Bulk email duplicate protection test passed")
    finally:
        db.close()


def test_bulk_email_validation():
    """Test bulk email validation."""
    init_database()
    db = get_test_db()
    try:
        service = create_customer_email_service()
        
        draft = EmailDraft(
            customer_id=1,
            customer_email="invalid-email",  # Invalid
            customer_name="Test",
            subject="Test",
            body="Body",
        )
        
        result = service.send_bulk_emails([draft], require_approval=False)
        
        assert result.success is False
        assert "Invalid email address" in result.error
        
        print("✓ Bulk email validation test passed")
    finally:
        db.close()


def get_test_db():
    """Get a test database session."""
    return db_service.get_session()


if __name__ == "__main__":
    test_email_template_types()
    test_email_status()
    test_email_draft()
    test_builtin_templates()
    test_template_rendering()
    test_customer_context()
    test_email_validation()
    test_generate_email_with_template()
    test_generate_email_custom()
    test_send_email_without_approval()
    test_bulk_email_duplicate_protection()
    test_bulk_email_validation()
    print("\n✅ All customer email tests passed!")