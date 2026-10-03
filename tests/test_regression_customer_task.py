"""Regression test for customer task creation routing."""

import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing (must be done BEFORE any other imports)
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
from src.agents.base_agent import create_agent, WorkflowType
from src.db import get_db
import app


def _uid(prefix: str = "TST") -> str:
    """Generate unique test ID."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _mock_agent_response(workflow_type: str, action: str, parameters: dict):
    """Create a mock LLM response for the given workflow/action/params."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "workflow_type": workflow_type,
        "action": action,
        "parameters": parameters,
        "confidence": 0.9,
        "reasoning": "Test reasoning"
    })
    return mock_response


def test_regression_customer_task_routing():
    """Regression test for the exact user request:
    'Create a task to call John Doe tomorrow.'
    
    Expected:
    - Route to support_followup/create_task
    - Resolve customer by name
    - Use actual tomorrow date
    - Create task successfully
    """
    reset_database()
    init_database()
    
    # Create test customer John Doe
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
    
    # Test the exact user request with mocked LLM
    agent = create_agent()
    
    mock_response = _mock_agent_response(
        workflow_type="support_followup",
        action="create_task",
        parameters={
            "customer_name": "John Doe",
            "title": "Call John Doe",
            "description": "Call John Doe tomorrow",
            "due_date": "2026-09-27T09:00:00",
            "priority": "medium",
            "approval_required": "optional"
        }
    )
    
    with patch.object(agent.client.chat.completions, 'create', return_value=mock_response):
        response = agent.process("Create a task to call John Doe tomorrow.")
    
    # Verify routing
    assert response.workflow_type == WorkflowType.SUPPORT_FOLLOWUP
    assert response.action == "create_task"
    assert response.parameters.get("customer_name") == "John Doe"
    assert "due_date" in response.parameters
    assert response.parameters["priority"] == "medium"
    
    # Execute workflow
    result = app.execute_workflow(response)
    
    # Verify execution success
    assert result.success
    assert result.data["customer_name"] == "John Doe"
    assert result.data["customer_id"] == customer.customer_id
    assert "task_id" in result.data
    assert result.data["title"] == "Call John Doe"
    assert "due_date" in result.data


def test_regression_high_priority_customer_task():
    """Test high-priority customer task creation."""
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
    
    agent = create_agent()
    
    mock_response = _mock_agent_response(
        workflow_type="support_followup",
        action="create_task",
        parameters={
            "customer_name": "Jane Smith",
            "title": "Contact Jane Smith",
            "description": "High-priority task to contact Jane Smith",
            "due_date": "2026-09-27T09:00:00",
            "priority": "high",
            "approval_required": "optional"
        }
    )
    
    with patch.object(agent.client.chat.completions, 'create', return_value=mock_response):
        response = agent.process("Create a high-priority task to contact Jane Smith tomorrow.")
    
    assert response.workflow_type == WorkflowType.SUPPORT_FOLLOWUP
    assert response.action == "create_task"
    assert response.parameters.get("priority") == "high"
    assert response.parameters.get("customer_name") == "Jane Smith"
    
    result = app.execute_workflow(response)
    assert result.success
    assert result.data["priority"] == 80


def test_regression_unknown_customer_no_invent():
    """Test that unknown customer doesn't trigger task creation."""
    reset_database()
    init_database()
    
    agent = create_agent()
    
    mock_response = _mock_agent_response(
        workflow_type="support_followup",
        action="create_task",
        parameters={
            "customer_name": "Rahul Sharma",
            "title": "Call Rahul Sharma",
            "description": "Call unknown customer Rahul Sharma",
            "due_date": "2026-09-27T09:00:00",
            "priority": "medium",
            "approval_required": "optional"
        }
    )
    
    with patch.object(agent.client.chat.completions, 'create', return_value=mock_response):
        response = agent.process("Create a task to call unknown customer Rahul Sharma tomorrow.")
    
    # Should still route to support_followup but execution should fail gracefully
    assert response.workflow_type == WorkflowType.SUPPORT_FOLLOWUP
    assert response.action == "create_task"
    assert response.parameters.get("customer_name") == "Rahul Sharma"
    
    result = app.execute_workflow(response)
    assert not result.success
    assert "Customer not found" in result.error


if __name__ == "__main__":
    test_regression_customer_task_routing()
    test_regression_high_priority_customer_task()
    test_regression_unknown_customer_no_invent()
    print("All regression tests passed!")