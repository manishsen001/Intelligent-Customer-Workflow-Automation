"""Customer actions for workflow tools."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from openai import OpenAI

from src.config.logging_config import logger
from src.config.settings import settings
from src.core.tools import BaseTool
from src.core.workflow_models import ToolResult, WorkflowExecutionContext, ToolParameter, ToolSchema
from src.db import get_db
from src.db.repositories import CustomerRepository, TaskRepository, FollowUpRepository, ReminderRepository
from src.db.models import (
    Customer, 
    Task, 
    TaskStatus, 
    FollowUp,
    FollowUpStatus,
    Reminder,
    CustomerSegment,
    CustomerStatus,
    PaymentStatus,
    SupportStatus,
    ApprovalStatus,
)
from src.workflows.reminder import ReminderFrequency
from src.services.customer_intelligence import create_customer_intelligence, CustomerAnalysis
from src.services.approval import create_approval_service
from src.services.customer_email import (
    create_customer_email_service,
    EmailTemplateType,
    EmailStatus,
    EmailDraft,
)


class CustomerSearchTool(BaseTool):
    """Tool for searching customers with various filters."""
    
    def _get_description(self) -> str:
        return "Search and filter customers by segment, status, payment status, support status, and custom criteria."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="customer_search",
            description=self._get_description(),
            parameters=[
                ToolParameter("segment", "string", "Customer segment filter", required=False,
                             enum=[s.value for s in CustomerSegment]),
                ToolParameter("status", "string", "Customer status filter", required=False,
                             enum=[s.value for s in CustomerStatus]),
                ToolParameter("payment_status", "string", "Payment status filter", required=False,
                             enum=[s.value for s in PaymentStatus]),
                ToolParameter("support_status", "string", "Support status filter", required=False,
                             enum=[s.value for s in SupportStatus]),
                ToolParameter("min_priority", "integer", "Minimum priority score", required=False),
                ToolParameter("has_outstanding", "boolean", "Filter customers with outstanding amount > 0", required=False),
                ToolParameter("search", "string", "Search by name, email, customer_id, or company", required=False),
                ToolParameter("limit", "integer", "Maximum number of results", required=False, default=50),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        repo = CustomerRepository(db)
        
        filters = {}
        if parameters.get("segment"):
            filters["segment"] = parameters["segment"]
        if parameters.get("status"):
            filters["status"] = parameters["status"]
        if parameters.get("payment_status"):
            filters["payment_status"] = parameters["payment_status"]
        if parameters.get("support_status"):
            filters["support_status"] = parameters["support_status"]
        if parameters.get("min_priority") is not None:
            filters["min_priority"] = parameters["min_priority"]
        if parameters.get("has_outstanding"):
            filters["has_outstanding"] = True
        if parameters.get("search"):
            filters["search"] = parameters["search"]
        
        limit = parameters.get("limit", 50)
        customers = repo.list_customers(filters=filters, limit=limit)
        
        # Convert to serializable format
        customer_data = []
        for c in customers:
            customer_data.append({
                "id": c.id,
                "customer_id": c.customer_id,
                "name": c.name,
                "email": c.email,
                "company": c.company,
                "customer_type": c.customer_type.value,
                "customer_status": c.customer_status.value,
                "customer_segment": c.customer_segment.value if c.customer_segment else None,
                "total_purchase_value": c.total_purchase_value,
                "order_count": c.order_count,
                "payment_status": c.payment_status.value,
                "outstanding_amount": c.outstanding_amount,
                "support_status": c.support_status.value,
                "priority": c.priority,
                "last_contact_date": c.last_contact_date.isoformat() if c.last_contact_date else None,
                "last_purchase_date": c.last_purchase_date.isoformat() if c.last_purchase_date else None,
            })
        
        # Store in context for subsequent steps
        context.selected_customers = customer_data
        
        return ToolResult(
            success=True,
            data={
                "customers": customer_data,
                "count": len(customer_data),
                "filters_applied": filters,
            },
        )


class CustomerAnalysisTool(BaseTool):
    """Tool for AI-powered customer analysis."""
    
    def __init__(self):
        super().__init__()
        self.intelligence = create_customer_intelligence()
    
    def _get_description(self) -> str:
        return "Analyze customers using AI to generate insights, segments, scores, and recommendations."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="customer_analysis",
            description=self._get_description(),
            parameters=[
                ToolParameter("customer_ids", "array", "List of customer IDs to analyze", required=True,
                             default=[]),
                ToolParameter("use_ai", "boolean", "Whether to use AI for deeper analysis", required=False, default=True),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        repo = CustomerRepository(db)
        
        customer_ids = parameters.get("customer_ids", [])
        use_ai = parameters.get("use_ai", True)
        
        if not customer_ids:
            if not context.selected_customers:
                return ToolResult(success=False, error="No customers selected for analysis")
            customer_ids = [c["customer_id"] for c in context.selected_customers]
        
        customers = []
        for cid in customer_ids:
            customer = repo.get_by_customer_id(cid)
            if customer:
                customers.append(customer)
        
        if not customers:
            return ToolResult(success=False, error=f"No customers found for IDs: {customer_ids}")
        
        analyses = self.intelligence.batch_analyze(customers, use_ai=use_ai)
        
        # Update customer records with analysis
        for customer, analysis in zip(customers, analyses):
            self.intelligence.update_customer_scores(customer, analysis)
        
        db.commit()
        
        analysis_data = []
        for analysis in analyses:
            analysis_data.append({
                "customer_id": analysis.customer_id,
                "summary": analysis.summary,
                "segment": analysis.segment.value,
                "segment_reasoning": analysis.segment_reasoning,
                "engagement_score": analysis.engagement_score.normalized,
                "value_score": analysis.value_score.normalized,
                "churn_risk": analysis.churn_risk.normalized,
                "follow_up_priority": analysis.follow_up_priority.normalized,
                "recommended_action": analysis.recommended_action,
                "recommended_communication_type": analysis.recommended_communication_type,
                "priority": analysis.priority,
                "confidence": analysis.confidence,
            })
        
        return ToolResult(
            success=True,
            data={
                "analyses": analysis_data,
                "count": len(analysis_data),
            },
        )


class CreateCustomerFollowUpTool(BaseTool):
    """Tool for creating customer follow-ups."""
    
    def _get_description(self) -> str:
        return "Create a follow-up task for one or more customers with title, reason, due date, and priority."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="create_customer_follow_up",
            description=self._get_description(),
            parameters=[
                ToolParameter("customer_ids", "array", "List of customer IDs to create follow-ups for", required=True),
                ToolParameter("title", "string", "Follow-up title", required=True),
                ToolParameter("reason", "string", "Reason for follow-up", required=True),
                ToolParameter("due_date", "string", "Due date in ISO format (YYYY-MM-DDTHH:MM:SS)", required=True),
                ToolParameter("priority", "integer", "Priority (1-100)", required=False, default=50),
                ToolParameter("assigned_to", "string", "Assigned user/team", required=False),
                ToolParameter("next_action", "string", "Next action description", required=False),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        repo = FollowUpRepository(db)
        customer_repo = CustomerRepository(db)
        
        customer_ids = parameters.get("customer_ids", [])
        if not customer_ids:
            if not context.selected_customers:
                return ToolResult(success=False, error="No customers selected for follow-up creation")
            customer_ids = [c["customer_id"] for c in context.selected_customers]
        
        try:
            due_date = datetime.fromisoformat(parameters["due_date"])
        except ValueError:
            return ToolResult(success=False, error="Invalid due_date format. Use ISO format YYYY-MM-DDTHH:MM:SS")
        
        if due_date < datetime.now():
            return ToolResult(success=False, error="Due date must be in the future")
        
        follow_ups_created = []
        for cid in customer_ids:
            customer = db.query(Customer).filter(Customer.customer_id == cid).first()
            if not customer:
                logger.warning(f"Customer {cid} not found, skipping")
                continue
            
            follow_up = FollowUp(
                customer_id=customer.id,
                title=parameters.get("title", f"Follow up with {customer.name}"),
                reason=parameters.get("reason", ""),
                status=FollowUpStatus.PENDING,
                priority=parameters.get("priority", 50),
                due_date=due_date,
                next_action=parameters.get("next_action"),
            )
            repo.create(follow_up)
            follow_ups_created.append({
                "follow_up_id": follow_up.id,
                "customer_id": cid,
                "title": follow_up.title,
                "due_date": follow_up.due_date.isoformat() if follow_up.due_date else None,
            })
        
        db.commit()
        
        return ToolResult(
            success=True,
            data={
                "follow_ups_created": follow_ups_created,
                "count": len(follow_ups_created),
            },
        )


class UpdateCustomerFollowUpTool(BaseTool):
    """Tool for updating customer follow-up status."""
    
    def _get_description(self) -> str:
        return "Update the status of a customer follow-up (pending, in_progress, waiting_approval, completed, cancelled, overdue)."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="update_customer_follow_up",
            description=self._get_description(),
            parameters=[
                ToolParameter("follow_up_id", "integer", "Follow-up ID", required=True),
                ToolParameter("status", "string", "New status", required=True,
                             enum=["pending", "in_progress", "waiting_approval", "completed", "cancelled", "overdue"]),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        from src.services.follow_up import create_follow_up_service
        
        db = next(get_db())
        service = create_follow_up_service(db)
        
        follow_up_id = parameters["follow_up_id"]
        status = parameters["status"]
        
        try:
            result = service.update_follow_up_status(follow_up_id, status)
            return ToolResult(success=result["success"], data=result, error=result.get("error"))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GetCustomerFollowUpsTool(BaseTool):
    """Tool for retrieving customer follow-ups."""
    
    def _get_description(self) -> str:
        return "Get follow-ups for customers with optional filters (pending, upcoming, overdue, high priority)."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="get_customer_follow_ups",
            description=self._get_description(),
            parameters=[
                ToolParameter("customer_ids", "array", "List of customer IDs", required=False),
                ToolParameter("status", "string", "Filter by status", required=False,
                             enum=["pending", "in_progress", "waiting_approval", "completed", "cancelled", "overdue"]),
                ToolParameter("type", "string", "Type of follow-ups to retrieve", required=False, default="pending",
                             enum=["pending", "upcoming", "overdue", "high_priority", "all"]),
                ToolParameter("days", "integer", "Days ahead for upcoming", required=False, default=7),
                ToolParameter("min_priority", "integer", "Minimum priority for high priority", required=False, default=50),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        from src.services.follow_up import create_follow_up_service
        
        db = next(get_db())
        service = create_follow_up_service(db)
        
        type_param = parameters.get("type", "pending")
        status = parameters.get("status")
        
        if type_param == "pending":
            follow_ups = service.list_follow_ups(status=status)
        elif type_param == "upcoming":
            days = parameters.get("days", 7)
            follow_ups = service.get_upcoming_follow_ups(days=days)
        elif type_param == "overdue":
            follow_ups = service.get_overdue_follow_ups()
        elif type_param == "high_priority":
            min_priority = parameters.get("min_priority", 50)
            follow_ups = service.get_high_priority_follow_ups(min_priority=min_priority)
        else:
            follow_ups = service.list_follow_ups(status=status)
        
        follow_up_data = []
        for fu in follow_ups:
            follow_up_data.append({
                "id": fu.id,
                "customer_id": fu.customer_id,
                "title": fu.title,
                "reason": fu.reason,
                "status": fu.status.value,
                "priority": fu.priority,
                "due_date": fu.due_date.isoformat() if fu.due_date else None,
                "next_action": fu.next_action,
            })
        
        return ToolResult(
            success=True,
            data={
                "follow_ups": follow_up_data,
                "count": len(follow_up_data),
            },
        )


class CustomerSegmentTool(BaseTool):
    """Tool for customer segmentation."""
    
    def _get_description(self) -> str:
        return "Segment customers based on various criteria and get segment distribution."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="customer_segment",
            description=self._get_description(),
            parameters=[
                ToolParameter("segment", "string", "Filter by segment", required=False,
                             enum=[s.value for s in ["new_customer", "active_customer", "loyal_customer", "at_risk_customer", "inactive_customer", "high_value_customer", "potential_lead", "payment_risk"]]),
                ToolParameter("filters", "object", "Additional filters", required=False, default={}),
                ToolParameter("limit", "integer", "Maximum number of customers", required=False, default=1000),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        from src.services.customer_intelligence import create_customer_intelligence
        
        db = next(get_db())
        repo = CustomerRepository(db)
        intelligence = create_customer_intelligence()
        
        segment = parameters.get("segment")
        filters = parameters.get("filters", {})
        limit = parameters.get("limit", 1000)
        
        if segment:
            filters["segment"] = segment
        
        customers = repo.list_customers(filters=filters, limit=limit)
        
        if not customers:
            return ToolResult(success=True, data={"segments": {}, "total": 0, "message": "No customers found"})
        
        analyses = intelligence.batch_analyze(customers, use_ai=False)
        
        segments = {}
        for customer, analysis in zip(customers, analyses):
            segment = analysis.segment.value
            if segment not in segments:
                segments[segment] = {
                    "name": segment.replace("_", " ").title(),
                    "count": 0,
                    "customers": [],
                }
            segments[segment]["count"] += 1
            segments[segment]["customers"].append({
                "customer_id": customer.customer_id,
                "name": customer.name,
                "email": customer.email,
                "priority": analysis.priority,
            })
        
        return ToolResult(
            success=True,
            data={
                "segments": segments,
                "total": len(customers),
            },
        )


def register_customer_tools() -> None:
    """Register all customer-specific tools in the global registry."""
    from src.core.tools import tool_registry
    
    tools = [
        CustomerSearchTool(),
        CustomerAnalysisTool(),
        CreateCustomerFollowUpTool(),
        UpdateCustomerFollowUpTool(),
        GetCustomerFollowUpsTool(),
        CustomerSegmentTool(),
    ]
    
    for tool in tools:
        tool_registry.register(tool)
    
    logger.info(f"Registered {len(tools)} customer tools: {tool_registry.get_tool_names()}")