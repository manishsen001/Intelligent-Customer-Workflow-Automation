"""Tests for Customer Intelligence module."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
import os
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.services.customer_intelligence import (
    CustomerIntelligence,
    CustomerScore,
    create_customer_intelligence,
)
from src.db.models import (
    Customer,
    CustomerSegment,
    CustomerStatus,
    CustomerType,
    PaymentStatus,
    SupportStatus,
)


def create_test_customer(
    customer_id: str = "TEST001",
    name: str = "Test Customer",
    total_purchase_value: float = 5000,
    order_count: int = 5,
    days_since_contact: int = 10,
    days_since_purchase: int = 20,
    payment_status: PaymentStatus = PaymentStatus.CURRENT,
    outstanding_amount: float = 0,
    support_status: SupportStatus = SupportStatus.NONE,
) -> Customer:
    """Create a test customer."""
    now = datetime.now()
    return Customer(
        customer_id=customer_id,
        name=name,
        email=f"{customer_id.lower()}@example.com",
        company="Test Corp",
        customer_type=CustomerType.COMPANY,
        total_purchase_value=total_purchase_value,
        order_count=order_count,
        last_contact_date=now - timedelta(days=days_since_contact),
        last_purchase_date=now - timedelta(days=days_since_purchase),
        payment_status=payment_status,
        outstanding_amount=outstanding_amount,
        support_status=support_status,
        customer_status=CustomerStatus.ACTIVE,
        priority=10,
    )


def test_engagement_score():
    """Test engagement score calculation."""
    ci = create_customer_intelligence()

    # High engagement
    customer = create_test_customer(days_since_contact=3, days_since_purchase=5, order_count=15)
    score = ci.calculate_engagement_score(customer)
    assert score.normalized > 0.7
    assert "Recent contact" in " ".join(score.factors)

    # Medium engagement
    customer = create_test_customer(days_since_contact=15, days_since_purchase=30, order_count=5)
    score = ci.calculate_engagement_score(customer)
    assert 0.3 <= score.normalized <= 0.7

    # Low engagement
    customer = create_test_customer(days_since_contact=60, days_since_purchase=100, order_count=1)
    score = ci.calculate_engagement_score(customer)
    assert score.normalized <= 0.3

    print("✓ Engagement score tests passed")


def test_value_score():
    """Test value score calculation."""
    ci = create_customer_intelligence()

    # High value
    customer = create_test_customer(total_purchase_value=20000, order_count=15)
    score = ci.calculate_value_score(customer)
    assert score.normalized > 0.7
    assert "High total value" in " ".join(score.factors)

    # Medium value
    customer = create_test_customer(total_purchase_value=5000, order_count=5)
    score = ci.calculate_value_score(customer)
    assert 0.3 <= score.normalized <= 0.7

    # Low value
    customer = create_test_customer(total_purchase_value=500, order_count=1)
    score = ci.calculate_value_score(customer)
    assert score.normalized < 0.5

    print("✓ Value score tests passed")


def test_churn_risk():
    """Test churn risk calculation."""
    ci = create_customer_intelligence()

    # High churn risk
    customer = create_test_customer(
        days_since_contact=100,
        payment_status=PaymentStatus.OVERDUE,
        outstanding_amount=500,
        support_status=SupportStatus.OPEN,
    )
    score = ci.calculate_churn_risk(customer)
    assert score.normalized > 0.5
    assert any("churn risk" in f.lower() or "no contact" in f.lower() for f in score.factors)

    # Low churn risk
    customer = create_test_customer(
        days_since_contact=5,
        payment_status=PaymentStatus.CURRENT,
        outstanding_amount=0,
        support_status=SupportStatus.NONE,
    )
    score = ci.calculate_churn_risk(customer)
    assert score.normalized < 0.3

    print("✓ Churn risk tests passed")


def test_follow_up_priority():
    """Test follow-up priority calculation."""
    ci = create_customer_intelligence()

    # High priority - high value + churn risk
    customer = create_test_customer(
        total_purchase_value=15000,
        days_since_contact=60,
        payment_status=PaymentStatus.OVERDUE,
    )
    score = ci.calculate_follow_up_priority(customer)
    assert score.normalized > 0.5

    # Low priority - low value, no issues
    customer = create_test_customer(
        total_purchase_value=500,
        days_since_contact=5,
        payment_status=PaymentStatus.CURRENT,
    )
    score = ci.calculate_follow_up_priority(customer)
    assert score.normalized < 0.5

    print("✓ Follow-up priority tests passed")


def test_segment_determination():
    """Test customer segment determination."""
    ci = create_customer_intelligence()

    # High value
    customer = create_test_customer(total_purchase_value=15000, order_count=15, days_since_contact=5)
    engagement = ci.calculate_engagement_score(customer)
    value = ci.calculate_value_score(customer)
    churn = ci.calculate_churn_risk(customer)
    follow_up = ci.calculate_follow_up_priority(customer)
    segment, reasoning = ci.determine_segment(customer, engagement, value, churn, follow_up)
    assert segment == CustomerSegment.HIGH_VALUE_CUSTOMER

    # Payment risk
    customer = create_test_customer(payment_status=PaymentStatus.OVERDUE, outstanding_amount=2000)
    engagement = ci.calculate_engagement_score(customer)
    value = ci.calculate_value_score(customer)
    churn = ci.calculate_churn_risk(customer)
    follow_up = ci.calculate_follow_up_priority(customer)
    segment, reasoning = ci.determine_segment(customer, engagement, value, churn, follow_up)
    assert segment == CustomerSegment.PAYMENT_RISK

    # At risk
    customer = create_test_customer(days_since_contact=90)
    engagement = ci.calculate_engagement_score(customer)
    value = ci.calculate_value_score(customer)
    churn = ci.calculate_churn_risk(customer)
    follow_up = ci.calculate_follow_up_priority(customer)
    segment, reasoning = ci.determine_segment(customer, engagement, value, churn, follow_up)
    assert segment == CustomerSegment.AT_RISK_CUSTOMER

    # Inactive
    customer = create_test_customer(days_since_contact=45, total_purchase_value=1000, order_count=1)
    engagement = ci.calculate_engagement_score(customer)
    value = ci.calculate_value_score(customer)
    churn = ci.calculate_churn_risk(customer)
    follow_up = ci.calculate_follow_up_priority(customer)
    segment, reasoning = ci.determine_segment(customer, engagement, value, churn, follow_up)
    assert segment == CustomerSegment.INACTIVE_CUSTOMER

    print("✓ Segment determination tests passed")


def test_full_analysis():
    """Test full customer analysis."""
    ci = create_customer_intelligence()

    customer = create_test_customer(
        customer_id="ANALYSIS001",
        name="Analysis Test",
        total_purchase_value=12000,
        order_count=8,
        days_since_contact=15,
        days_since_purchase=30,
    )

    analysis = ci.analyze_customer(customer, use_ai=False)

    assert analysis.customer_id == "ANALYSIS001"
    assert analysis.segment in CustomerSegment
    assert analysis.engagement_score is not None
    assert analysis.value_score is not None
    assert analysis.churn_risk is not None
    assert analysis.follow_up_priority is not None
    assert analysis.recommended_action
    assert analysis.recommended_communication_type
    assert 0 <= analysis.priority <= 100
    assert 0 <= analysis.confidence <= 1

    print("✓ Full analysis tests passed")


def test_score_normalization():
    """Test score normalization."""
    ci = create_customer_intelligence()

    # Test edge cases
    score = CustomerScore(score=0, factors=[], max_score=10)
    assert score.normalized == 0.0

    score = CustomerScore(score=10, factors=[], max_score=10)
    assert score.normalized == 1.0

    score = CustomerScore(score=15, factors=[], max_score=10)
    assert score.normalized == 1.0  # Capped at 1.0

    score = CustomerScore(score=-5, factors=[], max_score=10)
    assert score.normalized == 0.0  # Floored at 0.0

    print("✓ Score normalization tests passed")


if __name__ == "__main__":
    test_engagement_score()
    test_value_score()
    test_churn_risk()
    test_follow_up_priority()
    test_segment_determination()
    test_full_analysis()
    test_score_normalization()
    print("\n✅ All customer intelligence tests passed!")