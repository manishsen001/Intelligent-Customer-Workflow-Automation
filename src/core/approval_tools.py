"""Approval tools for workflow automation."""

from datetime import datetime
from typing import Any, Optional

from src.config.logging_config import logger
from src.core.tools import BaseTool
from src.core.workflow_models import ToolParameter, ToolSchema, ToolResult, WorkflowExecutionContext
from src.db import get_db
from src.db.models import Approval, ApprovalStatus
from src.services.approval import create_approval_service


class RequestApprovalTool(BaseTool):
    """Tool for requesting approval for sensitive actions."""
    
    def _get_description(self) -> str:
        return "Request human approval for sensitive actions like sending emails, bulk operations, or external notifications."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="request_approval",
            description=self._get_description(),
            parameters=[
                ToolParameter("approval_type", "string", "Type of approval (e.g., send_email, bulk_email, campaign_send, external_notification)", required=True),
                ToolParameter("title", "string", "Short title for the approval request", required=True),
                ToolParameter("description", "string", "Detailed description of what needs approval", required=True),
                ToolParameter("content", "object", "The content requiring approval (e.g., email draft, task details)", required=True),
                ToolParameter("customer_ids", "array", "List of customer IDs affected by this action", required=False, default=[]),
                ToolParameter("requires_approval", "boolean", "Whether this action requires approval", required=False, default=True),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        approval_service = create_approval_service(db)
        
        approval_type = parameters["approval_type"]
        title = parameters["title"]
        description = parameters["description"]
        content = parameters["content"]
        customer_ids = parameters.get("customer_ids", [])
        requires_approval = parameters.get("requires_approval", True)
        
        # Get workflow execution ID from context
        workflow_execution_id = context.variables.get("workflow_execution_id")
        
        # Create approval
        approval = approval_service.create_approval(
            approval_type=approval_type,
            title=title,
            description=description,
            content=content,
            workflow_execution_id=workflow_execution_id,
            customer_id=customer_ids[0] if customer_ids else None,
        )
        
        if not requires_approval:
            # Auto-approve if not required
            approval = approval_service.approve(approval.id, "system", "Auto-approved (approval not required)")
            return ToolResult(
                success=True,
                data={
                    "approval_id": approval.id,
                    "status": "auto_approved",
                    "message": "Action auto-approved (approval not required)",
                },
            )
        
        return ToolResult(
            success=True,
            data={
                "approval_id": approval.id,
                "status": "pending",
                "message": f"Approval requested for: {title}",
                "approval_details": {
                    "type": approval_type,
                    "title": title,
                    "description": description,
                    "content": content,
                    "customer_ids": customer_ids,
                },
            },
        )


class ApproveActionTool(BaseTool):
    """Tool for approving a pending approval request."""
    
    def _get_description(self) -> str:
        return "Approve a pending approval request."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="approve_action",
            description=self._get_description(),
            parameters=[
                ToolParameter("approval_id", "integer", "ID of the approval to approve", required=True),
                ToolParameter("comments", "string", "Optional approval comments", required=False),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        approval_service = create_approval_service(db)
        
        approval_id = parameters["approval_id"]
        comments = parameters.get("comments")
        reviewer = context.variables.get("user", "system")
        
        try:
            approval = approval_service.approve(approval_id, reviewer, comments)
            return ToolResult(
                success=True,
                data={
                    "approval_id": approval.id,
                    "status": approval.status.value,
                    "message": f"Approval {approval_id} approved",
                },
            )
        except ValueError as e:
            return ToolResult(success=False, error=str(e))


class RejectActionTool(BaseTool):
    """Tool for rejecting a pending approval request."""
    
    def _get_description(self) -> str:
        return "Reject a pending approval request with a reason."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="reject_action",
            description=self._get_description(),
            parameters=[
                ToolParameter("approval_id", "integer", "ID of the approval to reject", required=True),
                ToolParameter("reason", "string", "Reason for rejection", required=True),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        approval_service = create_approval_service(db)
        
        approval_id = parameters["approval_id"]
        reason = parameters["reason"]
        reviewer = context.variables.get("user", "system")
        
        try:
            approval = approval_service.reject(approval_id, reviewer, reason)
            return ToolResult(
                success=True,
                data={
                    "approval_id": approval.id,
                    "status": approval.status.value,
                    "message": f"Approval {approval_id} rejected",
                    "rejection_reason": reason,
                },
            )
        except ValueError as e:
            return ToolResult(success=False, error=str(e))


class EditApprovalTool(BaseTool):
    """Tool for editing an approval request content."""
    
    def _get_description(self) -> str:
        return "Edit the content of a pending approval request."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="edit_approval",
            description=self._get_description(),
            parameters=[
                ToolParameter("approval_id", "integer", "ID of the approval to edit", required=True),
                ToolParameter("new_content", "object", "New content for the approval", required=True),
                ToolParameter("comments", "string", "Optional edit comments", required=False),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        approval_service = create_approval_service(db)
        
        approval_id = parameters["approval_id"]
        new_content = parameters["new_content"]
        comments = parameters.get("comments")
        editor = context.variables.get("user", "system")
        
        try:
            approval = approval_service.edit(approval_id, editor, new_content, comments)
            return ToolResult(
                success=True,
                data={
                    "approval_id": approval.id,
                    "status": approval.status.value,
                    "message": f"Approval {approval_id} edited",
                    "new_content": new_content,
                },
            )
        except ValueError as e:
            return ToolResult(success=False, error=str(e))


class ListApprovalsTool(BaseTool):
    """Tool for listing approvals with filters."""
    
    def _get_description(self) -> str:
        return "List approvals with optional status filter."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="list_approvals",
            description=self._get_description(),
            parameters=[
                ToolParameter("status", "string", "Filter by status (pending, approved, rejected, edited)", required=False),
                ToolParameter("limit", "integer", "Maximum number of results", required=False, default=50),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        approval_service = create_approval_service(db)
        
        status_str = parameters.get("status")
        limit = parameters.get("limit", 50)
        
        status = None
        if status_str:
            try:
                status = ApprovalStatus(status_str)
            except ValueError:
                return ToolResult(success=False, error=f"Invalid status: {status_str}")
        
        approvals = approval_service.list_approvals(status=status, limit=limit)
        
        approval_data = []
        for a in approvals:
            approval_data.append({
                "id": a.id,
                "approval_type": a.approval_type,
                "title": a.title,
                "description": a.description,
                "content": a.content,
                "status": a.status.value,
                "requested_by": a.requested_by,
                "approved_by": a.approved_by,
                "approved_at": a.approved_at.isoformat() if a.approved_at else None,
                "rejection_reason": a.rejection_reason,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat(),
                "customer_id": a.customer_id,
                "workflow_execution_id": a.workflow_execution_id,
            })
        
        return ToolResult(
            success=True,
            data={
                "approvals": approval_data,
                "count": len(approval_data),
            },
        )


def register_approval_tools() -> None:
    """Register approval tools in the global registry."""
    from src.core.tools import tool_registry
    
    tools = [
        RequestApprovalTool(),
        ApproveActionTool(),
        RejectActionTool(),
        EditApprovalTool(),
        ListApprovalsTool(),
    ]
    
    for tool in tools:
        tool_registry.register(tool)
    
    logger.info(f"Registered {len(tools)} approval tools")


# Auto-register on import
register_approval_tools()