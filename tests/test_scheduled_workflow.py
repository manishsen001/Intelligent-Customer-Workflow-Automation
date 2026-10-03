"""Tests for scheduled workflow engine."""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
import os
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.db import init_database, db_service
from src.db.models import (
    ScheduledWorkflow,
    ScheduledWorkflowExecution,
    ScheduledWorkflowStatus,
    ScheduledWorkflowFrequency,
)
from src.services.scheduled_workflow import (
    ScheduledWorkflowEngine,
    create_scheduled_workflow_engine,
)
from src.core.workflow_models import WorkflowPlan, WorkflowStep, ActionType, ApprovalRequired, WorkflowType


def get_test_db():
    """Get a test database session."""
    return db_service.get_session()


def init_test_db():
    """Initialize a fresh test database."""
    db_service.drop_db()
    db_service.init_db()


def test_scheduled_workflow_creation():
    """Test creating a scheduled workflow."""
    init_test_db()
    db = get_test_db()
    try:
        from src.services.scheduled_workflow import ScheduledWorkflowEngine
        engine = ScheduledWorkflowEngine(db)
    
        workflow_plan = WorkflowPlan(
            plan_id="test_plan",
            workflow_type=WorkflowType.CUSTOMER_FOLLOWUP,
            name="Test Workflow",
            description="Test",
            target_customers={},
            steps=[
                WorkflowStep(
                    step_id="step_1",
                    action=ActionType.CUSTOMER_SEARCH,
                    description="Test",
                    parameters={},
                )
            ],
        )
    
        workflow = engine.create_scheduled_workflow(
            workflow_id="test_workflow_1",
            workflow_name="Test Workflow",
            description="Test workflow",
            frequency=ScheduledWorkflowFrequency.DAILY,
            schedule_config={"time": "09:00"},
            workflow_plan=workflow_plan,
        )
    
        # Check values immediately (before session might close)
        assert workflow.workflow_id == "test_workflow_1"
        assert workflow.workflow_name == "Test Workflow"
        assert workflow.status == ScheduledWorkflowStatus.ACTIVE
        assert workflow.frequency == ScheduledWorkflowFrequency.DAILY
        assert workflow.schedule_config["time"] == "09:00"
        
        print("✓ Scheduled workflow creation test passed")
    finally:
        db.close()


def test_calculate_next_run_daily():
    """Test next run calculation for daily workflows."""
    init_database()
    db = get_test_db()
    try:
        engine = create_scheduled_workflow_engine(db)
        
        # Create a workflow
        workflow = ScheduledWorkflow(
            workflow_id="test_daily",
            workflow_name="Daily Test",
            description="Test",
            frequency=ScheduledWorkflowFrequency.DAILY,
            schedule_config={"time": "10:00"},
            workflow_plan={},
            status=ScheduledWorkflowStatus.ACTIVE,
        )
        db.add(workflow)
        db.commit()
        
        next_run = engine.calculate_next_run(workflow)
        assert next_run is not None
        assert next_run.hour == 10
        assert next_run.minute == 0
        
        print("✓ Daily next run calculation test passed")
    finally:
        db.close()


def test_calculate_next_run_weekly():
    """Test next run calculation for weekly workflows."""
    init_database()
    db = get_test_db()
    try:
        engine = create_scheduled_workflow_engine(db)
        
        workflow = ScheduledWorkflow(
            workflow_id="test_weekly",
            workflow_name="Weekly Test",
            description="Test",
            frequency=ScheduledWorkflowFrequency.WEEKLY,
            schedule_config={"day_of_week": 0, "time": "09:00"},  # Monday
            workflow_plan={},
            status=ScheduledWorkflowStatus.ACTIVE,
        )
        db.add(workflow)
        db.commit()
        
        next_run = engine.calculate_next_run(workflow)
        assert next_run is not None
        assert next_run.hour == 9
        assert next_run.minute == 0
        assert next_run.weekday() == 0  # Monday
        
        print("✓ Weekly next run calculation test passed")
    finally:
        db.close()


def test_calculate_next_run_monthly():
    """Test next run calculation for monthly workflows."""
    init_database()
    db = get_test_db()
    try:
        engine = create_scheduled_workflow_engine(db)
        
        workflow = ScheduledWorkflow(
            workflow_id="test_monthly",
            workflow_name="Monthly Test",
            description="Test",
            frequency=ScheduledWorkflowFrequency.MONTHLY,
            schedule_config={"day_of_month": 15, "time": "10:00"},
            workflow_plan={},
            status=ScheduledWorkflowStatus.ACTIVE,
        )
        db.add(workflow)
        db.commit()
        
        next_run = engine.calculate_next_run(workflow)
        assert next_run is not None
        assert next_run.hour == 10
        assert next_run.minute == 0
        assert next_run.day == 15
        
        print("✓ Monthly next run calculation test passed")
    finally:
        db.close()


def test_workflow_pause_resume_disable():
    """Test pause, resume, disable workflow operations."""
    init_database()
    db = get_test_db()
    try:
        engine = create_scheduled_workflow_engine(db)
        
        workflow = ScheduledWorkflow(
            workflow_id="test_pause_resume",
            workflow_name="Pause Resume Test",
            description="Test",
            frequency=ScheduledWorkflowFrequency.DAILY,
            schedule_config={"time": "09:00"},
            workflow_plan={},
            status=ScheduledWorkflowStatus.ACTIVE,
        )
        db.add(workflow)
        db.commit()
        
        # Pause
        result = engine.pause_workflow("test_pause_resume")
        assert result is True
        
        # Resume
        result = engine.resume_workflow("test_pause_resume")
        assert result is True
        
        # Disable
        result = engine.disable_workflow("test_pause_resume")
        assert result is True
        
        print("✓ Pause/Resume/Disable test passed")
    finally:
        db.close()


def test_natural_language_scheduling():
    """Test natural language scheduling via workflow planner."""
    init_database()
    db = get_test_db()
    try:
        from src.core.workflow_planner import create_workflow_planner
        planner = create_workflow_planner()
        
        # Test that planner can be created
        assert planner is not None
        
        print("✓ Natural language scheduling test passed (planner creation)")
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
    
    test_scheduled_workflow_creation()
    test_calculate_next_run_daily()
    test_calculate_next_run_weekly()
    test_calculate_next_run_monthly()
    test_workflow_pause_resume_disable()
    test_natural_language_scheduling()
    
    print("\n✅ All scheduled workflow tests passed!")