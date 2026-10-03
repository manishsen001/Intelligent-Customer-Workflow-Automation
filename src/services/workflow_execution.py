"""Workflow Execution Service for persisting user inputs and AI/system outputs."""

import json
from datetime import datetime, timezone
from typing import Any, Optional, List

from src.config.logging_config import logger
from src.db import db_service
from src.db.models import WorkflowExecution, WorkflowStatus
from src.db.repositories import WorkflowExecutionRepository


class WorkflowExecutionService:
    """Service for managing workflow executions with input/output persistence."""
    
    def __init__(self):
        """Initialize workflow execution service."""
        pass
    
    def _execute_in_transaction(self, func):
        """Execute a function within a database transaction."""
        session = db_service.get_session()
        try:
            result = func(session)
            session.commit()
            if result is not None and hasattr(result, '__table__'):
                session.refresh(result)
                session.expunge(result)
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_execution(
        self,
        workflow_id: str,
        workflow_name: str,
        trigger_type: str,
        trigger_data: Optional[dict] = None,
        input_data: Optional[dict] = None,
        customer_id: Optional[int] = None,
    ) -> WorkflowExecution:
        """Create a new workflow execution record."""
        def _create(session):
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                trigger_type=trigger_type,
                trigger_data=trigger_data,
                input_data=input_data,
                customer_id=customer_id,
                status=WorkflowStatus.PENDING,
            )
            repo = WorkflowExecutionRepository(session)
            return repo.create(execution)
        return self._execute_in_transaction(_create)
    
    def update_execution_output(
        self,
        execution_id: int,
        output_data: Optional[dict] = None,
        result_summary: Optional[str] = None,
        status: WorkflowStatus = WorkflowStatus.COMPLETED,
        error_message: Optional[str] = None,
        execution_log: Optional[list] = None,
    ) -> WorkflowExecution:
        """Update workflow execution with output/results."""
        def _update(session):
            repo = WorkflowExecutionRepository(session)
            execution = repo.get_by_id(execution_id)
            if not execution:
                raise ValueError(f"Workflow execution {execution_id} not found")
            
            if output_data is not None:
                execution.output_data = output_data
            if result_summary is not None:
                execution.result_summary = result_summary
            if status is not None:
                execution.status = status
            if error_message is not None:
                execution.error_message = error_message
            if execution_log is not None:
                execution.execution_log = execution_log
            
            execution.completed_at = datetime.now(timezone.utc)
            execution.updated_at = datetime.now(timezone.utc)
            
            result = WorkflowExecutionRepository(session).update(execution)
            logger.info(f"Updated workflow execution {execution_id} with status {status.value}")
            return result
        
        return self._execute_in_transaction(_update)
    
    def mark_failed(
        self,
        execution_id: int,
        error_message: str,
        execution_log: Optional[list] = None,
    ) -> WorkflowExecution:
        """Mark workflow execution as failed."""
        return self.update_execution_output(
            execution_id=execution_id,
            status=WorkflowStatus.FAILED,
            error_message=error_message,
            execution_log=execution_log,
        )
    
    def get_execution(self, execution_id: int) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID."""
        return self._execute_in_transaction(
            lambda session: WorkflowExecutionRepository(session).get_by_id(execution_id)
        )
    
    def get_execution_by_workflow_id(self, workflow_id: str) -> Optional[WorkflowExecution]:
        """Get latest workflow execution by workflow ID."""
        return self._execute_in_transaction(
            lambda session: WorkflowExecutionRepository(session).get_by_workflow_id(workflow_id)
        )
    
    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowExecution]:
        """List workflow executions with optional filters."""
        def _list(session):
            repo = WorkflowExecutionRepository(session)
            return repo.list_executions(
                workflow_id=workflow_id,
                customer_id=customer_id,
                status=status,
                skip=skip,
                limit=limit,
            )
        return self._execute_in_transaction(_list)
    
    def get_execution_history(self, customer_id: Optional[int] = None, limit: int = 100) -> List[WorkflowExecution]:
        """Get workflow execution history for a customer."""
        def _get_history(session):
            repo = WorkflowExecutionRepository(session)
            executions = repo.list_executions(customer_id=customer_id, limit=limit)
            for exec in executions:
                session.expunge(exec)
            return executions
        return self._execute_in_transaction(_get_history)


def create_workflow_execution_service() -> WorkflowExecutionService:
    """Factory function to create workflow execution service."""
    return WorkflowExecutionService()
