"""Test for Follow-up Start button action."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.db import init_database, reset_database
from src.db import get_db
from src.db.models import Customer, CustomerStatus, CustomerType, FollowUp, FollowUpStatus
from src.db.repositories import CustomerRepository, FollowUpRepository
from src.services.follow_up import create_follow_up_service
from datetime import datetime, timedelta


def test_start_action_changes_status_to_in_progress():
    """Test that Start button changes follow-up status from pending to in_progress."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    # Create test customer
    customer = Customer(
        customer_id="TEST-CUST-001",
        name="Test Customer",
        email="test@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    follow_up_service = create_follow_up_service()
    
    # Create a pending follow-up
    follow_up = follow_up_service.create_follow_up(
        customer_id="TEST-CUST-001",
        reason="Test follow-up",
        due_date=datetime.now() + timedelta(days=2),
        priority=50,
        next_action="Test action",
    )
    
    assert follow_up.status == FollowUpStatus.PENDING
    
    # Simulate clicking Start button - call update_status
    updated_follow_up = follow_up_service.update_status(follow_up.id, "in_progress")
    
    assert updated_follow_up.status == FollowUpStatus.IN_PROGRESS
    assert updated_follow_up.updated_at is not None
    
    # Verify the change is persisted by querying with a fresh session
    from src.db import get_db as get_db_fresh
    db_fresh = next(get_db_fresh())
    fresh_repo = FollowUpRepository(db_fresh)
    refreshed = fresh_repo.get_by_id(follow_up.id)
    
    assert refreshed.status == FollowUpStatus.IN_PROGRESS


def test_start_action_persists_to_database():
    """Test that Start action persists status change to database."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    customer = Customer(
        customer_id="TEST-CUST-002",
        name="Test Customer 2",
        email="test2@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    follow_up_service = create_follow_up_service()
    
    # Create a pending follow-up
    follow_up = follow_up_service.create_follow_up(
        customer_id="TEST-CUST-002",
        reason="Test follow-up for start action",
        due_date=datetime.now() + timedelta(days=1),
        priority=75,
        next_action="Call customer",
    )
    
    # Update status via Start action
    updated = follow_up_service.update_status(follow_up.id, "in_progress")
    
    # Verify the change is in the database by checking with a fresh session
    from src.db import get_db as get_db_fresh
    db_fresh = next(get_db_fresh())
    fresh_repo = FollowUpRepository(db_fresh)
    refreshed = fresh_repo.get_by_id(follow_up.id)
    
    assert refreshed.status == FollowUpStatus.IN_PROGRESS


if __name__ == "__main__":
    test_start_action_changes_status_to_in_progress()
    test_start_action_persists_to_database()
    print("All Start action tests passed!")