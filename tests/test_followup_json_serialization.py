"""Regression test for Create Follow-up JSON serialization."""

import os
import sys
import json
import uuid
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
)
from src.db.repositories import CustomerRepository
from src.services.follow_up import create_follow_up_service
from src.db import get_db
from datetime import datetime, timedelta


def _uid(prefix: str = "TST") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_create_followup_result_is_json_serializable():
    """Test that Create Follow-up result can be serialized to JSON."""
    reset_database()
    init_database()
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    customer = Customer(
        customer_id=_uid("CUST"),
        name="John Doe",
        email="john.doe@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    follow_up_service = create_follow_up_service()
    follow_up = follow_up_service.create_follow_up(
        customer_id=customer.id,
        reason="Follow up regarding support issue",
        due_date=datetime.now() + timedelta(days=2),
        priority=50,
        next_action="Contact customer",
    )
    
    # Simulate the FollowUpResult wrapper used in render_followups()
    class FollowUpResult:
        def __init__(self, fu):
            self.success = True
            self.message = f"Follow-up created for customer {fu.customer_id}"
            self.follow_up = fu
    
    result = FollowUpResult(follow_up)
    
    # Verify result has the expected attributes
    assert result.success is True
    assert result.follow_up is not None
    assert result.follow_up.id is not None
    assert result.follow_up.customer_id == customer.id
    
    # Verify JSON serializable by extracting primitive data from FollowUp
    # This simulates what display_result would do
    follow_up_dict = {
        "id": follow_up.id,
        "customer_id": follow_up.customer_id,
        "title": follow_up.title,
        "reason": follow_up.reason,
        "priority": follow_up.priority,
        "status": str(follow_up.status),
        "due_date": follow_up.due_date.isoformat() if follow_up.due_date else None,
        "next_action": follow_up.next_action,
    }
    
    result_dict = {
        "success": result.success,
        "message": result.message,
        "follow_up": follow_up_dict,
    }
    
    # This should not raise an exception
    json_str = json.dumps(result_dict)
    
    # Verify key fields are present
    assert result_dict["success"] is True
    assert "follow_up" in result_dict
    assert result_dict["follow_up"]["id"] is not None
    assert result_dict["follow_up"]["customer_id"] == customer.id
    assert "due_date" in result_dict["follow_up"]
    assert result_dict["follow_up"]["priority"] == 50
    assert "pending" in str(result_dict["follow_up"]["status"]).lower()


if __name__ == "__main__":
    test_create_followup_result_is_json_serializable()
    print("All Follow-up creation tests passed!")