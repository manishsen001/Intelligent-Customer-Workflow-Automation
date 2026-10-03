"""Regression tests for workflow execution input/output persistence."""

import os
import sys
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
    WorkflowExecution,
    WorkflowStatus,
)
from src.db.repositories import CustomerRepository, WorkflowExecutionRepository
from src.services.workflow_execution import create_workflow_execution_service
from src.db import get_db
from datetime import datetime, timedelta


def _uid(prefix: str = "TST") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_workflow_execution_creation_and_persistence():
    """Test that workflow execution is created and persisted."""
    reset_database()
    init_database()
    
    service = create_workflow_execution_service()
    
    # Create execution with input data
    execution = service.create_execution(
        workflow_id="test-workflow-001",
        workflow_name="Test Workflow",
        trigger_type="user_request",
        trigger_data={"action": "send_email"},
        input_data={"recipient": "test@example.com", "subject": "Test"},
        customer_id=None,
    )
    
    assert execution is not None
    assert execution.workflow_id == "test-workflow-001"
    assert execution.trigger_data == {"action": "send_email"}
    assert execution.input_data == {"recipient": "test@example.com", "subject": "Test"}
    assert execution.status == WorkflowStatus.PENDING
    
    # Verify persistence with fresh session
    execution2 = service.get_execution(execution.id)
    assert execution2 is not None
    assert execution2.workflow_id == "test-workflow-001"
    assert execution2.input_data == {"recipient": "test@example.com", "subject": "Test"}


def test_workflow_execution_output_persistence():
    """Test that workflow execution output/results are persisted."""
    reset_database()
    init_database()
    
    service = create_workflow_execution_service()
    
    # Create execution
    execution = service.create_execution(
        workflow_id="test-workflow-002",
        workflow_name="Test Workflow 2",
        trigger_type="ai_chat",
        trigger_data={"message": "Hello"},
        input_data={"user_message": "Hello"},
    )
    
    # Update with output
    updated = service.update_execution_output(
        execution_id=execution.id,
        output_data={"response": "Hello! How can I help?"},
        result_summary="AI responded to greeting",
        status=WorkflowStatus.COMPLETED,
        execution_log=[{"step": "ai_response", "output": "Hello! How can I help?"}],
    )
    
    assert updated.output_data == {"response": "Hello! How can I help?"}
    assert updated.result_summary == "AI responded to greeting"
    assert updated.status == WorkflowStatus.COMPLETED
    assert updated.execution_log == [{"step": "ai_response", "output": "Hello! How can I help?"}]
    
    # Verify persistence with fresh session
    refreshed = service.get_execution(execution.id)
    assert refreshed.output_data == {"response": "Hello! How can I help?"}
    assert refreshed.status == WorkflowStatus.COMPLETED


def test_workflow_execution_failure_persistence():
    """Test that failed workflow execution stores error info."""
    reset_database()
    init_database()
    
    service = create_workflow_execution_service()
    
    execution = service.create_execution(
        workflow_id="test-workflow-003",
        workflow_name="Test Workflow 3",
        trigger_type="email_send",
        trigger_data={"to": "test@example.com"},
        input_data={"to": "test@example.com", "subject": "Test"},
    )
    
    # Mark as failed
    failed = service.mark_failed(
        execution_id=execution.id,
        error_message="SMTP connection timeout",
        execution_log=[{"step": "smtp_connect", "error": "timeout"}],
    )
    
    assert failed.status == WorkflowStatus.FAILED
    assert failed.error_message == "SMTP connection timeout"
    assert failed.execution_log == [{"step": "smtp_connect", "error": "timeout"}]
    
    # Verify persistence
    refreshed = service.get_execution(execution.id)
    assert refreshed.status == WorkflowStatus.FAILED
    assert refreshed.error_message == "SMTP connection timeout"


def test_workflow_execution_history():
    """Test workflow execution history retrieval."""
    reset_database()
    init_database()
    
    from src.db import get_db
    from src.db.models import Customer, CustomerStatus, CustomerType
    from src.db.repositories import CustomerRepository
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    customer = Customer(
        customer_id="HIST-001",
        name="History Test Customer",
        email="history@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    service = create_workflow_execution_service()
    
    # Create multiple executions for the same customer
    for i in range(3):
        service.create_execution(
            workflow_id=f"hist-workflow-{i}",
            workflow_name=f"History Workflow {i}",
            trigger_type="test",
            trigger_data={"index": i},
            input_data={"data": f"input {i}"},
            customer_id=customer.id,
        )
    
    # Get history
    history = service.get_execution_history(customer_id=customer.id, limit=10)
    
    assert len(history) == 3
    for exec in history:
        assert exec.customer_id == customer.id
        assert exec.workflow_id.startswith("hist-workflow-")


def test_workflow_execution_input_data_is_stored():
    """Test that user inputs are stored correctly."""
    reset_database()
    init_database()
    
    service = create_workflow_execution_service()
    
    # Test various input data types
    test_inputs = [
        {"type": "email", "to": "test@test.com", "subject": "Test", "body": "Hello"},
        {"type": "task", "action": "create", "params": {"name": "Test Task"}},
        {"type": "reminder", "time": "2025-01-15T10:00:00", "message": "Meeting"},
        {"type": "customer_analysis", "customer_id": "CUST001"},
    ]
    
    for i, input_data in enumerate(test_inputs):
        execution = service.create_execution(
            workflow_id=f"input-test-{i}",
            workflow_name=f"Input Test {i}",
            trigger_type="user_input",
            input_data=input_data,
        )
        
        # Verify input is stored
        refreshed = service.get_execution(execution.id)
        assert refreshed.input_data == input_data
        assert refreshed.trigger_type == "user_input"


if __name__ == "__main__":
    test_workflow_execution_creation_and_persistence()
    test_workflow_execution_output_persistence()
    test_workflow_execution_failure_persistence()
    test_workflow_execution_history()
    test_workflow_execution_input_data_is_stored()
    print("All workflow execution persistence tests passed!")
