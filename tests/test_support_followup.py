"""Tests for support_followup workflow."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.db import init_database, reset_database
from src.db.models import (
    Customer,
    CustomerStatus,
    CustomerType,
    Task,
    TaskStatus,
)
from src.db.repositories import CustomerRepository, TaskRepository
from src.db import get_db
import app


def _uid(prefix: str = "TST") -> str:
    """Generate unique test ID."""
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_support_followup_create_task_existing_customer():
    """Test create_task for an existing customer."""
    reset_database()
    init_database()
    
    # Create test customer
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    customer = Customer(
        customer_id=_uid("CUST"),
        name="John Doe",
        email="john@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    # Execute create_task
    result = app.execute_support_followup("create_task", {
        "customer_name": "John Doe",
        "title": "Contact about support issue",
        "description": "High-priority follow-up",
        "priority": "high",
        "due_date": "2025-01-16",
    })
    
    assert result.success
    assert result.data["customer_name"] == "John Doe"
    assert result.data["title"] == "Contact about support issue"
    assert result.data["priority"] == 80  # high = 80
    assert result.data["status"] == "pending"
    assert "task_id" in result.data


def test_support_followup_create_task_high_priority():
    """Test high-priority task creation."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    from src.db.models import Customer, CustomerStatus, CustomerType
    customer = Customer(
        customer_id=_uid("CUST"),
        name="Jane Smith",
        email="jane@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    result = app.execute_support_followup("create_task", {
        "customer_id": customer.customer_id,
        "title": "Urgent follow-up",
        "priority": "high",
    })
    
    assert result.success
    assert result.data["priority"] == 80


def test_support_followup_create_task_medium_priority():
    """Test medium-priority task creation."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    from src.db.models import Customer, CustomerStatus, CustomerType
    customer = Customer(
        customer_id=_uid("CUST"),
        name="Bob Wilson",
        email="bob@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    result = app.execute_support_followup("create_task", {
        "customer_name": "Bob Wilson",
        "title": "Regular follow-up",
        "priority": "medium",
    })
    
    assert result.success
    assert result.data["priority"] == 50


def test_support_followup_create_task_low_priority():
    """Test low-priority task creation."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    from src.db.models import Customer, CustomerStatus, CustomerType
    customer = Customer(
        customer_id=_uid("CUST"),
        name="Alice Brown",
        email="alice@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    result = app.execute_support_followup("create_task", {
        "customer_name": "Alice Brown",
        "title": "Low priority follow-up",
        "priority": "low",
    })
    
    assert result.success
    assert result.data["priority"] == 20


def test_support_followup_create_task_missing_customer():
    """Test create_task with unknown customer."""
    reset_database()
    init_database()
    
    result = app.execute_support_followup("create_task", {
        "customer_name": "Unknown Customer",
        "title": "Task for unknown",
        "priority": "high",
    })
    
    assert not result.success
    assert "Customer not found" in result.error


def test_support_followup_create_task_with_due_date():
    """Test task creation with due date."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    from src.db.models import Customer, CustomerStatus, CustomerType
    customer = Customer(
        customer_id=_uid("CUST"),
        name="Charlie Davis",
        email="charlie@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    result = app.execute_support_followup("create_task", {
        "customer_name": "Charlie Davis",
        "title": "Follow-up with deadline",
        "priority": "high",
        "due_date": "2025-02-15",
    })
    
    assert result.success
    assert result.data["due_date"] == "2025-02-15T00:00:00"


def test_support_followup_create_task_success_result():
    """Test that successful task creation returns complete task info."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    from src.db.models import Customer, CustomerStatus, CustomerType
    customer = Customer(
        customer_id=_uid("CUST"),
        name="Diana Evans",
        email="diana@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    result = app.execute_support_followup("create_task", {
        "customer_name": "Diana Evans",
        "title": "Test task",
        "description": "Test description",
        "priority": "medium",
    })
    
    assert result.success
    assert "task_id" in result.data
    assert result.data["customer_id"] == customer.customer_id
    assert result.data["customer_name"] == "Diana Evans"
    assert result.data["title"] == "Test task"
    assert result.data["description"] == "Test description"
    assert result.data["priority"] == 50
    assert result.data["status"] == "pending"
    assert "created_at" in result.data


if __name__ == "__main__":
    test_support_followup_create_task_existing_customer()
    test_support_followup_create_task_high_priority()
    test_support_followup_create_task_medium_priority()
    test_support_followup_create_task_low_priority()
    test_support_followup_create_task_missing_customer()
    test_support_followup_create_task_with_due_date()
    test_support_followup_create_task_success_result()
    print("All support_followup tests passed!")