"""Tests for display_result function and result handling."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
import os
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.workflows.task_automation import TaskResult
from src.workflows.email_automation import EmailResult
from src.workflows.reminder import ReminderResult, Reminder, ReminderFrequency


def test_task_result_success():
    """Test TaskResult with success."""
    result = TaskResult(
        success=True,
        output="File written successfully",
        execution_time=0.5
    )
    assert result.success is True
    assert result.output == "File written successfully"
    assert result.error is None
    assert result.execution_time == 0.5


def test_task_result_failure():
    """Test TaskResult with failure."""
    result = TaskResult(
        success=False,
        output="",
        error="File not found: test.txt",
        execution_time=0.1
    )
    assert result.success is False
    assert result.error == "File not found: test.txt"
    assert result.output == ""


def test_email_result_success():
    """Test EmailResult with success."""
    result = EmailResult(
        success=True,
        message="Email sent successfully to test@example.com",
        details={"recipients": ["test@example.com"], "subject": "Test"}
    )
    assert result.success is True
    assert result.message == "Email sent successfully to test@example.com"
    assert result.details == {"recipients": ["test@example.com"], "subject": "Test"}


def test_email_result_failure():
    """Test EmailResult with failure."""
    result = EmailResult(
        success=False,
        message="",
        error="SMTP authentication failed"
    )
    assert result.success is False
    assert result.error == "SMTP authentication failed"
    assert result.message == ""


def test_reminder_result_success():
    """Test ReminderResult with success."""
    reminder = Reminder(
        id="abc123",
        title="Test Reminder",
        description="Test description",
        trigger_time="2025-01-01T10:00:00",
        frequency=ReminderFrequency.ONCE
    )
    result = ReminderResult(
        success=True,
        message="Reminder 'Test Reminder' set for 2025-01-01T10:00:00",
        reminder=reminder
    )
    assert result.success is True
    assert result.message == "Reminder 'Test Reminder' set for 2025-01-01T10:00:00"
    assert result.reminder == reminder


def test_reminder_result_list():
    """Test ReminderResult with list of reminders."""
    reminder1 = Reminder(
        id="abc123",
        title="Test 1",
        description="Desc 1",
        trigger_time="2025-01-01T10:00:00",
        frequency=ReminderFrequency.ONCE
    )
    reminder2 = Reminder(
        id="def456",
        title="Test 2",
        description="Desc 2",
        trigger_time="2025-01-02T10:00:00",
        frequency=ReminderFrequency.DAILY
    )
    result = ReminderResult(
        success=True,
        message="Found 2 reminders",
        reminders=[reminder1, reminder2]
    )
    assert result.success is True
    assert len(result.reminders) == 2


def test_task_result_output_types():
    """Test TaskResult with various output types."""
    # String output
    result = TaskResult(success=True, output="text output", execution_time=0.1)
    assert isinstance(result.output, str)
    
    # Dict output
    result = TaskResult(success=True, output={"key": "value"}, execution_time=0.1)
    assert isinstance(result.output, dict)
    
    # List output
    result = TaskResult(success=True, output=[1, 2, 3], execution_time=0.1)
    assert isinstance(result.output, list)
    
    # None output
    result = TaskResult(success=True, output=None, execution_time=0.1)
    assert result.output is None


if __name__ == "__main__":
    test_task_result_success()
    test_task_result_failure()
    test_email_result_success()
    test_email_result_failure()
    test_reminder_result_success()
    test_reminder_result_list()
    test_task_result_output_types()
    print("All result handling tests passed!")