"""Approval service for human-in-the-loop workflows."""

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.config.logging_config import logger
from src.db import db_service
from src.db.models import Approval, ApprovalStatus, WorkflowExecution
from src.db.repositories import ApprovalRepository, WorkflowExecutionRepository


class ApprovalService:
    """Service for managing approvals in workflow execution."""
    
    def __init__(self):
        """Initialize approval service."""
        pass
    
    def _execute_in_transaction(self, func):
        """Execute a function within a database transaction."""
        session = db_service.get_session()
        try:
            result = func(session)
            session.commit()
            # Only refresh/expunge single SQLAlchemy model instances
            if result is not None and hasattr(result, '__table__'):
                session.refresh(result)
                session.expunge(result)
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_approval(
        self,
        approval_type: str,
        title: str,
        description: str,
        content: dict,
        workflow_execution_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        requested_by: str = "system",
    ) -> Approval:
        """Create a new approval request."""
        def _create(session):
            approval = Approval(
                workflow_execution_id=workflow_execution_id,
                customer_id=customer_id,
                approval_type=approval_type,
                title=title,
                description=description,
                content=content,
                status=ApprovalStatus.PENDING,
                requested_by=requested_by,
            )
            repo = ApprovalRepository(session)
            return repo.create(approval)
        return self._execute_in_transaction(_create)
    
    def get_approval(self, approval_id: int) -> Optional[Approval]:
        """Get approval by ID."""
        return self._execute_in_transaction(
            lambda session: ApprovalRepository(session).get_by_id(approval_id)
        )
    
    def list_pending_approvals(self, limit: int = 100) -> list[Approval]:
        """List all pending approvals."""
        return self._execute_in_transaction(
            lambda session: ApprovalRepository(session).list_approvals(status=ApprovalStatus.PENDING, limit=limit)
        )
    
    def list_approvals(
        self,
        status: Optional[ApprovalStatus] = None,
        limit: int = 100,
    ) -> list[Approval]:
        """List approvals with optional status filter."""
        def _list(session):
            repo = ApprovalRepository(session)
            approvals = repo.list_approvals(status=status, limit=limit)
            # Expire and expunge each approval to avoid DetachedInstanceError
            for approval in approvals:
                session.refresh(approval)
                session.expunge(approval)
            return approvals
        return self._execute_in_transaction(_list)
    
    def approve(self, approval_id: int, reviewer: str, comments: Optional[str] = None) -> Approval:
        """Approve an approval request."""
        def _approve(session):
            repo = ApprovalRepository(session)
            approval = repo.get_by_id(approval_id)
            if not approval:
                raise ValueError(f"Approval {approval_id} not found")
            
            if approval.status != ApprovalStatus.PENDING:
                raise ValueError(f"Cannot approve: approval is {approval.status.value}")
            
            approval.status = ApprovalStatus.APPROVED
            approval.approved_by = reviewer
            approval.approved_at = datetime.now()
            if comments:
                approval.description = (approval.description or "") + f"\n\nApproval comment: {comments}"
            
            updated = repo.update(approval)
            
            # If this approval is linked to a workflow execution, check if we can resume
            if approval.workflow_execution_id:
                self._check_workflow_resume_in_session(session, approval.workflow_execution_id)
            
            logger.info(f"Approval {approval_id} approved by {reviewer}")
            return updated
        
        return self._execute_in_transaction(_approve)
    
    def reject(self, approval_id: int, reviewer: str, reason: str) -> Approval:
        """Reject an approval request."""
        def _reject(session):
            repo = ApprovalRepository(session)
            approval = repo.get_by_id(approval_id)
            if not approval:
                raise ValueError(f"Approval {approval_id} not found")
            
            if approval.status != ApprovalStatus.PENDING:
                raise ValueError(f"Cannot reject: approval is {approval.status.value}")
            
            approval.status = ApprovalStatus.REJECTED
            approval.approved_by = reviewer
            approval.approved_at = datetime.now()
            approval.rejection_reason = reason
            
            updated = repo.update(approval)
            
            logger.info(f"Approval {approval_id} rejected by {reviewer}: {reason}")
            return updated
        
        return self._execute_in_transaction(_reject)
    
    def edit(self, approval_id: int, editor: str, new_content: dict, comments: Optional[str] = None) -> Approval:
        """Edit an approval request content."""
        def _edit(session):
            repo = ApprovalRepository(session)
            approval = repo.get_by_id(approval_id)
            if not approval:
                raise ValueError(f"Approval {approval_id} not found")
            
            if approval.status != ApprovalStatus.PENDING:
                raise ValueError(f"Cannot edit: approval is {approval.status.value}")
            
            approval.content = new_content
            approval.status = ApprovalStatus.EDITED
            if comments:
                approval.description = (approval.description or "") + f"\n\nEdit comment: {comments}"
            
            updated = repo.update(approval)
            logger.info(f"Approval {approval_id} edited by {editor}")
            return updated
        
        return self._execute_in_transaction(_edit)
    
    def approve_all(self, approval_ids: list[int], reviewer: str) -> list[Approval]:
        """Approve multiple approvals at once."""
        results = []
        for approval_id in approval_ids:
            try:
                result = self.approve(approval_id, reviewer)
                results.append(result)
            except ValueError as e:
                logger.warning(f"Failed to approve {approval_id}: {e}")
        return results
    
    def reject_all(self, approval_ids: list[int], reviewer: str, reason: str) -> list[Approval]:
        """Reject multiple approvals at once."""
        results = []
        for approval_id in approval_ids:
            try:
                result = self.reject(approval_id, reviewer, reason)
                results.append(result)
            except ValueError as e:
                logger.warning(f"Failed to reject {approval_id}: {e}")
        return results
    
    def _check_workflow_resume_in_session(self, session, workflow_execution_id: int) -> None:
        """Check if workflow can resume after approval."""
        repo = WorkflowExecutionRepository(session)
        workflow = repo.get_by_id(workflow_execution_id)
        if not workflow:
            return
        
        # Check if all required approvals for this workflow are approved
        pending_approvals = ApprovalRepository(session).list_approvals(
            status=ApprovalStatus.PENDING
        )
        workflow_pending = [a for a in pending_approvals if a.workflow_execution_id == workflow_execution_id]
        
        if not workflow_pending:
            # All approvals resolved, update workflow status
            workflow.status = "running"  # Will be picked up by workflow executor
            repo.update(workflow)
            logger.info(f"Workflow {workflow_execution_id} ready to resume")
    
    def get_approval_history(self, customer_id: Optional[int] = None, limit: int = 100) -> list[Approval]:
        """Get approval history, optionally filtered by customer."""
        def _get_history(session):
            repo = ApprovalRepository(session)
            approvals = repo.list_approvals(limit=limit)
            if customer_id is not None:
                approvals = [a for a in approvals if a.customer_id == customer_id]
            return approvals
        return self._execute_in_transaction(_get_history)
    
    def get_approval_stats(self) -> dict:
        """Get approval statistics."""
        def _get_stats(session):
            repo = ApprovalRepository(session)
            all_approvals = repo.list_approvals(limit=10000)
            
            stats = {
                "total": len(all_approvals),
                "pending": sum(1 for a in all_approvals if a.status == ApprovalStatus.PENDING),
                "approved": sum(1 for a in all_approvals if a.status == ApprovalStatus.APPROVED),
                "rejected": sum(1 for a in all_approvals if a.status == ApprovalStatus.REJECTED),
                "edited": sum(1 for a in all_approvals if a.status == ApprovalStatus.EDITED),
            }
            
            # By type
            by_type = {}
            for a in all_approvals:
                by_type.setdefault(a.approval_type, {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "edited": 0})
                by_type[a.approval_type]["total"] += 1
                by_type[a.approval_type][a.status.value] += 1
            
            stats["by_type"] = by_type
            return stats
        
        return self._execute_in_transaction(_get_stats)


def create_approval_service(session=None) -> ApprovalService:
    """Factory function to create approval service.
    
    Args:
        session: Optional session (ignored, kept for backward compatibility)
    """
    return ApprovalService()
