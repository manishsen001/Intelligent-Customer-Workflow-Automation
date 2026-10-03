"""Scheduled Workflow Execution Engine for Customer Workflow Automation System."""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from src.config.logging_config import logger
from src.config.settings import settings
from src.db import get_db, db_service
from src.db.models import (
    ScheduledWorkflow,
    ScheduledWorkflowExecution,
    ScheduledWorkflowStatus,
    ScheduledWorkflowFrequency,
    WorkflowExecution,
    WorkflowStatus,
)
from src.db.repositories import (
    ScheduledWorkflowRepository,
    ScheduledWorkflowExecutionRepository,
    WorkflowExecutionRepository,
)
from src.core.workflow_planner import create_workflow_planner, WorkflowPlan
from src.core.workflow_models import WorkflowExecutionContext, ToolResult
from src.core.tools import tool_registry


class ScheduledWorkflowEngine:
    """Engine for executing scheduled workflows."""
    
    def __init__(self, session=None):
        self._session = session
        self._owns_session = session is None
        self.planner = create_workflow_planner()
    
    def _get_session(self):
        """Get database session."""
        if self._session:
            return self._session
        return next(get_db())
    
    def _close_session(self):
        """Close session if we own it."""
        if self._owns_session and self._session:
            self._session.close()
            self._session = None
    
    def calculate_next_run(self, workflow: ScheduledWorkflow) -> Optional[datetime]:
        """Calculate the next run time based on frequency and schedule_config."""
        config = workflow.schedule_config or {}
        now = datetime.now(timezone.utc)
        
        if workflow.frequency == ScheduledWorkflowFrequency.ONCE:
            # One-time execution
            if workflow.next_run and workflow.next_run > now:
                return workflow.next_run
            return None
        
        elif workflow.frequency == ScheduledWorkflowFrequency.DAILY:
            # Daily at specific time
            time_str = config.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run
        
        elif workflow.frequency == ScheduledWorkflowFrequency.WEEKLY:
            # Weekly on specific day and time
            day_of_week = config.get("day_of_week", 0)  # 0=Monday
            time_str = config.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            
            days_ahead = (day_of_week - now.weekday() + 7) % 7
            if days_ahead == 0:
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    days_ahead = 7
            if days_ahead > 0:
                next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_run
        
        elif workflow.frequency == ScheduledWorkflowFrequency.MONTHLY:
            # Monthly on specific day and time
            day_of_month = config.get("day_of_month", 1)
            time_str = config.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            
            try:
                next_run = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            except ValueError:
                # Handle month with fewer days
                import calendar
                last_day = calendar.monthrange(now.year, now.month)[1]
                next_run = now.replace(day=min(day_of_month, last_day), hour=hour, minute=minute, second=0, microsecond=0)
            
            if next_run <= now:
                # Next month
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            return next_run
        
        elif workflow.frequency == ScheduledWorkflowFrequency.CRON:
            # Cron expression - simplified implementation
            # In production, use a proper cron library like croniter
            cron_expr = config.get("cron_expression", "0 9 * * *")
            logger.warning(f"Cron scheduling not fully implemented: {cron_expr}")
            return None
        
        return None
    
    def get_due_workflows(self) -> List[ScheduledWorkflow]:
        """Get all workflows that are due to run."""
        db = next(get_db())
        repo = ScheduledWorkflowRepository(db)
        try:
            workflows = repo.get_due_workflows()
            now = datetime.now(timezone.utc)
            due_workflows = []
            for w in workflows:
                if w.next_run and w.next_run <= datetime.now(timezone.utc):
                    due_workflows.append(w)
            return due_workflows
        finally:
            db.close()
    
    def execute_workflow(self, workflow: ScheduledWorkflow, user_id: str = "system") -> ScheduledWorkflowExecution:
        """Execute a scheduled workflow."""
        db = next(get_db())
        workflow_repo = ScheduledWorkflowRepository(db)
        execution_repo = ScheduledWorkflowExecutionRepository(db)
        
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        
        # Create execution record
        execution = ScheduledWorkflowExecution(
            scheduled_workflow_id=workflow.id,
            execution_id=execution_id,
            workflow_plan=workflow.workflow_plan,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        execution = execution_repo.create(execution)
        
        try:
            # Execute the workflow plan
            context = WorkflowExecutionContext(plan=WorkflowPlan.from_dict(workflow.workflow_plan))
            context.variables["user"] = user_id
            context.variables["auto_approve"] = True  # Scheduled workflows auto-approve
            
            results = self.planner.execute_plan(context.plan, auto_approve=True, user_id=user_id)
            
            # Count results
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            # Update execution record
            execution.status = "completed" if failed == 0 else "failed"
            execution.completed_at = datetime.now(timezone.utc)
            execution.customers_processed = len(set(r.data.get("customer_id") for r in results if r.data and r.data.get("customer_id")))
            execution.actions_executed = len(results)
            
            if failed > 0:
                execution.errors = [r.error for r in results if not r.success and r.error]
            
            execution.result_summary = f"Processed {len(results)} actions: {successful} succeeded, {failed} failed"
            
            execution = execution_repo.update(execution)
            
            # Update workflow last run info
            workflow_repo = ScheduledWorkflowRepository(db)
            next_run = self.calculate_next_run(workflow)
            workflow_repo.update_last_run(
                workflow_id=workflow.id,
                last_run=datetime.now(timezone.utc),
                status=execution.status,
                result={
                    "execution_id": execution_id,
                    "actions_executed": execution.actions_executed,
                    "customers_processed": execution.customers_processed,
                    "errors": execution.errors,
                }
            )
            if next_run:
                workflow_repo.update_next_run(workflow.id, next_run)
            
            db.commit()
            logger.info(f"Scheduled workflow {workflow.workflow_id} executed: {execution.status}")
            return execution
            
        except Exception as e:
            logger.error(f"Scheduled workflow {workflow.workflow_id} execution failed: {e}")
            execution.status = "failed"
            execution.completed_at = datetime.now(timezone.utc)
            execution.errors = [str(e)]
            execution.result_summary = f"Execution failed: {str(e)}"
            execution = execution_repo.update(execution)
            db.commit()
            raise
        finally:
            db.close()
    
    def process_due_workflows(self, user_id: str = "system") -> List[ScheduledWorkflowExecution]:
        """Process all workflows that are due to run."""
        workflows = self.get_due_workflows()
        executions = []
        
        for workflow in workflows:
            try:
                execution = self.execute_workflow(workflow, user_id)
                executions.append(execution)
            except Exception as e:
                logger.error(f"Failed to execute workflow {workflow.workflow_id}: {e}")
        
        return executions
    
    def create_scheduled_workflow(
        self,
        workflow_id: str,
        workflow_name: str,
        description: str,
        frequency: ScheduledWorkflowFrequency,
        schedule_config: Dict[str, Any],
        workflow_plan: WorkflowPlan,
        max_runs: Optional[int] = None,
    ) -> ScheduledWorkflow:
        """Create a new scheduled workflow."""
        db = self._get_session()
        owns_session = self._owns_session
        try:
            repo = ScheduledWorkflowRepository(db)
            
            # Check if workflow_id already exists
            existing = repo.get_by_workflow_id(workflow_id)
            if existing:
                raise ValueError(f"Workflow with ID {workflow_id} already exists")
            
            # Calculate first run
            now = datetime.now(timezone.utc)
            workflow = ScheduledWorkflow(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                description=description,
                frequency=frequency,
                schedule_config=schedule_config,
                workflow_plan=workflow_plan.to_dict(),
                status=ScheduledWorkflowStatus.ACTIVE,
                next_run=self._calculate_first_run(frequency, schedule_config, now),
                max_runs=max_runs,
            )
            
            result = ScheduledWorkflowRepository(db).create(workflow)
            db.commit()
            return result
        finally:
            if owns_session:
                db.close()
    
    def _calculate_first_run(self, frequency: ScheduledWorkflowFrequency, config: Dict, now: datetime) -> Optional[datetime]:
        """Calculate first run time for a new workflow."""
        if frequency == ScheduledWorkflowFrequency.ONCE:
            time_str = config.get("time")
            if time_str:
                hour, minute = map(int, time_str.split(":"))
                run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if run_time <= now:
                    run_time += timedelta(days=1)
                return run_time
            return now + timedelta(hours=1)
        
        elif frequency == ScheduledWorkflowFrequency.DAILY:
            time_str = config.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if run_time <= now:
                run_time += timedelta(days=1)
            return run_time
        
        elif frequency == ScheduledWorkflowFrequency.WEEKLY:
            day_of_week = config.get("day_of_week", 0)
            time_str = config.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            days_ahead = (day_of_week - now.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            run_time = now + timedelta(days=days_ahead)
            return run_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        elif frequency == ScheduledWorkflowFrequency.MONTHLY:
            day_of_month = config.get("day_of_month", 1)
            time_str = config.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            try:
                run_time = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(now.year, now.month)[1]
                run_time = now.replace(day=min(day_of_month, last_day), hour=hour, minute=minute, second=0, microsecond=0)
            if run_time <= now:
                if now.month == 12:
                    run_time = run_time.replace(year=now.year + 1, month=1)
                else:
                    run_time = run_time.replace(month=now.month + 1)
            return run_time
        
        return now + timedelta(hours=1)
    
    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a scheduled workflow."""
        db = next(get_db())
        repo = ScheduledWorkflowRepository(db)
        workflow = repo.get_by_workflow_id(workflow_id)
        if workflow:
            workflow.status = ScheduledWorkflowStatus.PAUSED
            workflow.updated_at = datetime.now(timezone.utc)
            repo.update(workflow)
            db.commit()
            return True
        return False
    
    def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused scheduled workflow."""
        db = next(get_db())
        repo = ScheduledWorkflowRepository(db)
        workflow = repo.get_by_workflow_id(workflow_id)
        if workflow:
            workflow.status = ScheduledWorkflowStatus.ACTIVE
            workflow.updated_at = datetime.now(timezone.utc)
            # Recalculate next run
            workflow.next_run = self.calculate_next_run(workflow)
            repo.update(workflow)
            db.commit()
            return True
        return False
    
    def disable_workflow(self, workflow_id: str) -> bool:
        """Disable a scheduled workflow."""
        db = next(get_db())
        repo = ScheduledWorkflowRepository(db)
        workflow = repo.get_by_workflow_id(workflow_id)
        if workflow:
            workflow.status = ScheduledWorkflowStatus.DISABLED
            workflow.updated_at = datetime.now(timezone.utc)
            repo.update(workflow)
            db.commit()
            return True
        return False
    
    def get_workflow_executions(self, workflow_id: str, limit: int = 50) -> List[ScheduledWorkflowExecution]:
        """Get execution history for a workflow."""
        db = next(get_db())
        repo = ScheduledWorkflowExecutionRepository(db)
        try:
            return repo.list_executions(scheduled_workflow_id=workflow_id, limit=limit)
        finally:
            db.close()


def create_scheduled_workflow_engine(session=None) -> ScheduledWorkflowEngine:
    """Factory function to create scheduled workflow engine."""
    return ScheduledWorkflowEngine(session)