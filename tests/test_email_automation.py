"""Tests for email automation with customer lookup."""

import os
import sys
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing (must be done before importing settings)
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.db import init_database
from src.db.models import Customer, CustomerStatus, CustomerType
from src.db.repositories import CustomerRepository
from src.workflows.email_automation import EmailMessage, EmailResult
from src.db import get_db


def _unique_id(prefix: str) -> str:
    """Generate a unique ID for test isolation."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_customer_email_lookup_by_id():
    """Test looking up customer email by customer_id."""
    init_database()
    db = next(get_db())
    repo = CustomerRepository(db)
    
    # Create a test customer with unique ID
    customer_id = _unique_id("TEST-EMAIL")
    customer = Customer(
        customer_id=customer_id,
        name="Test Customer",
        email="test.customer@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    repo.create(customer)
    db.commit()
    
    # Look up by customer_id
    found = repo.get_by_customer_id(customer_id)
    assert found is not None
    assert found.email == "test.customer@example.com"
    assert found.name == "Test Customer"


def test_customer_email_lookup_by_name():
    """Test looking up customer email by name search."""
    init_database()
    db = next(get_db())
    repo = CustomerRepository(db)
    
    # Create a test customer with unique name
    customer_id = _unique_id("TEST-EMAIL")
    unique_name = f"Unique Test Name {uuid.uuid4().hex[:8]}"
    customer = Customer(
        customer_id=customer_id,
        name=unique_name,
        email="unique.test@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    repo.create(customer)
    db.commit()
    
    # Search by name
    customers = repo.list_customers(filters={"search": unique_name}, limit=1)
    assert len(customers) == 1
    assert customers[0].email == "unique.test@example.com"
    assert customers[0].customer_id == customer_id


def test_customer_not_found():
    """Test that unknown customer returns None."""
    init_database()
    db = next(get_db())
    repo = CustomerRepository(db)
    
    found = repo.get_by_customer_id("NONEXISTENT-CUSTOMER-" + uuid.uuid4().hex[:8])
    assert found is None
    
    customers = repo.list_customers(filters={"search": "Nonexistent Customer Name " + uuid.uuid4().hex[:8]}, limit=1)
    assert len(customers) == 0


def test_customer_without_email():
    """Test customer with no email address."""
    init_database()
    db = next(get_db())
    repo = CustomerRepository(db)
    
    # Create customer without email
    customer_id = _unique_id("TEST-NO-EMAIL")
    customer = Customer(
        customer_id=customer_id,
        name="Customer Without Email",
        email=None,
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    repo.create(customer)
    db.commit()
    
    found = repo.get_by_customer_id(customer_id)
    assert found is not None
    assert found.email is None


if __name__ == "__main__":
    test_customer_email_lookup_by_id()
    test_customer_email_lookup_by_name()
    test_customer_not_found()
    test_customer_without_email()
    print("All email automation tests passed!")