"""Regression test for Follow-up customer ID resolution."""

import os
import sys
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.db import init_database, reset_database
from src.db.models import Customer, CustomerStatus, CustomerType
from src.db.repositories import CustomerRepository
from src.services.follow_up import create_follow_up_service
from src.db import get_db
from datetime import datetime, timedelta


def _uid(prefix: str = "TST") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_followup_form_accepts_actual_customer_id():
    """Test that Follow-up service accepts actual database customer ID."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    customer = Customer(
        customer_id="RSL-2c7745-001",
        name="John Doe",
        email="john.doe@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    follow_up_service = create_follow_up_service()
    
    # Use the actual database customer_id (string format as from UI)
    follow_up = follow_up_service.create_follow_up(
        customer_id="RSL-2c7745-001",
        reason="Follow up regarding support issue",
        due_date=datetime.now() + timedelta(days=2),
        priority=50,
        next_action="Contact customer",
    )
    
    assert follow_up is not None
    assert follow_up.customer_id == customer.id  # internal integer ID
    assert follow_up.reason == "Follow up regarding support issue"
    assert follow_up.priority == 50
    assert follow_up.next_action == "Contact customer"


def test_followup_form_rejects_invalid_customer_id():
    """Test that Follow-up service rejects invalid customer ID."""
    reset_database()
    init_database()
    
    follow_up_service = create_follow_up_service()
    
    # Try with non-existent customer ID
    try:
        follow_up = follow_up_service.create_follow_up(
            customer_id="NONEXISTENT-CUST",
            reason="Test reason",
            due_date=datetime.now() + timedelta(days=2),
            priority=50,
            next_action="Test action",
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Customer not found" in str(e)


def test_customer_repository_loads_customers():
    """Test that CustomerRepository loads actual customers for UI selectbox."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    
    # Create multiple customers
    for i, (cid, name) in enumerate([
        ("RSL-2c7745-001", "John Doe"),
        ("RSL-2c7745-002", "Jane Smith"),
        ("RSL-2c7745-003", "Bob Wilson"),
    ]):
        customer = Customer(
            customer_id=cid,
            name=name,
            email=f"{name.lower().replace(' ', '.')}@example.com",
            customer_type=CustomerType.INDIVIDUAL,
            customer_status=CustomerStatus.ACTIVE,
        )
        customer_repo.create(customer)
    db.commit()
    
    # Load all customers (simulating UI selectbox population)
    customers = customer_repo.list_customers(limit=1000)
    
    assert len(customers) == 3
    customer_ids = [c.customer_id for c in customers]
    assert "RSL-2c7745-001" in customer_ids
    assert "RSL-2c7745-002" in customer_ids
    assert "RSL-2c7745-003" in customer_ids
    
    # Verify the format used in UI selectbox
    customer_options = {f"{c.name} ({c.customer_id})": c.customer_id for c in customers}
    expected_options = {
        "John Doe (RSL-2c7745-001)": "RSL-2c7745-001",
        "Jane Smith (RSL-2c7745-002)": "RSL-2c7745-002",
        "Bob Wilson (RSL-2c7745-003)": "RSL-2c7745-003",
    }
    assert customer_options == expected_options


if __name__ == "__main__":
    test_followup_form_accepts_actual_customer_id()
    test_followup_form_rejects_invalid_customer_id()
    test_customer_repository_loads_customers()
    print("All Follow-up customer ID tests passed!")