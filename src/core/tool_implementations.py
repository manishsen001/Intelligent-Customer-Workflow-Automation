"""Tool implementations for Customer Workflow Automation System."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from openai import OpenAI

from src.config.logging_config import logger
from src.config.settings import settings
from src.core.tools import BaseTool, tool_registry
from src.core.workflow_models import ToolResult, WorkflowExecutionContext, ToolParameter, ToolSchema
from src.db import get_db
from src.db.repositories import CustomerRepository, TaskRepository, ReminderRepository
from src.db.models import (
    Customer, 
    Task, 
    TaskStatus, 
    Reminder,
    ApprovalStatus,
    CustomerSegment,
    CustomerStatus,
    PaymentStatus,
    SupportStatus,
)
from src.services.customer_intelligence import create_customer_intelligence, CustomerAnalysis
from src.services.approval import create_approval_service
from src.services.customer_email import (
    create_customer_email_service,
    EmailTemplateType,
    EmailStatus,
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
            # Use customers from previous search step
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


class CreateTaskTool(BaseTool):
    """Tool for creating follow-up tasks for customers."""
    
    def _get_description(self) -> str:
        return "Create a follow-up task for one or more customers with title, description, due date, and priority."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="create_task",
            description=self._get_description(),
            parameters=[
                ToolParameter("customer_ids", "array", "List of customer IDs to create tasks for", required=True),
                ToolParameter("title", "string", "Task title", required=True),
                ToolParameter("description", "string", "Task description", required=False, default=""),
                ToolParameter("task_type", "string", "Type of task", required=False, default="follow_up"),
                ToolParameter("due_date", "string", "Due date in ISO format (YYYY-MM-DDTHH:MM:SS)", required=False),
                ToolParameter("priority", "integer", "Task priority (1-100)", required=False, default=10),
                ToolParameter("assigned_to", "string", "Assigned user/team", required=False),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        repo = TaskRepository(db)
        
        customer_ids = parameters.get("customer_ids", [])
        if not customer_ids:
            if not context.selected_customers:
                return ToolResult(success=False, error="No customers selected for task creation")
            customer_ids = [c["customer_id"] for c in context.selected_customers]
        
        due_date = None
        if parameters.get("due_date"):
            try:
                due_date = datetime.fromisoformat(parameters["due_date"])
            except ValueError:
                return ToolResult(success=False, error="Invalid due_date format. Use ISO format YYYY-MM-DDTHH:MM:SS")
        
        tasks_created = []
        for cid in customer_ids:
            customer = db.query(Customer).filter(Customer.customer_id == cid).first()
            if not customer:
                logger.warning(f"Customer {cid} not found, skipping task creation")
                continue
            
            task = Task(
                customer_id=customer.id,
                title=parameters["title"],
                description=parameters.get("description", ""),
                task_type=parameters.get("task_type", "follow_up"),
                status=TaskStatus.PENDING,
                priority=parameters.get("priority", 10),
                due_date=due_date,
                assigned_to=parameters.get("assigned_to"),
            )
            repo.create(task)
            tasks_created.append({
                "task_id": task.id,
                "customer_id": cid,
                "title": task.title,
                "due_date": task.due_date.isoformat() if task.due_date else None,
            })
        
        db.commit()
        
        return ToolResult(
            success=True,
            data={
                "tasks_created": tasks_created,
                "count": len(tasks_created),
            },
        )


class GenerateEmailTool(BaseTool):
    """Tool for generating personalized email drafts for customers."""
    
    def __init__(self):
        super().__init__()
        self._llm_client: Optional[OpenAI] = None
    
    def _get_llm_client(self) -> OpenAI:
        if self._llm_client is None:
            llm_config = settings.get_llm_config()
            self._llm_client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"],
            )
        return self._llm_client
    
    def _get_description(self) -> str:
        return "Generate personalized email drafts for customers based on their profile, segment, and context."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="generate_email",
            description=self._get_description(),
            parameters=[
                ToolParameter("customer_ids", "array", "List of customer IDs to generate emails for", required=True),
                ToolParameter("purpose", "string", "Purpose of the email", required=True,
                             enum=["follow_up", "re_engagement", "payment_reminder", "welcome", "support_followup", "high_value_checkin", "custom"]),
                ToolParameter("custom_purpose", "string", "Custom purpose description (if purpose is 'custom')", required=False),
                ToolParameter("tone", "string", "Email tone", required=False, default="professional",
                             enum=["professional", "friendly", "formal", "casual", "urgent"]),
                ToolParameter("include_discount", "boolean", "Whether to include a discount offer", required=False, default=False),
                ToolParameter("discount_details", "string", "Details of discount offer if included", required=False),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        email_service = create_customer_email_service()
        
        customer_ids = parameters.get("customer_ids", [])
        if not customer_ids:
            if not context.selected_customers:
                return ToolResult(success=False, error="No customers selected for email generation")
            customer_ids = [c["customer_id"] for c in context.selected_customers]
        
        purpose_str = parameters.get("purpose", "follow_up")
        tone = parameters.get("tone", "professional")
        include_discount = parameters.get("include_discount", False)
        discount_details = parameters.get("discount_details", "")
        custom_purpose = parameters.get("custom_purpose", "")
        
        # Map purpose string to template type
        purpose_map = {
            "follow_up": EmailTemplateType.FOLLOW_UP,
            "re_engagement": EmailTemplateType.RE_ENGAGEMENT,
            "payment_reminder": EmailTemplateType.PAYMENT_REMINDER,
            "welcome": EmailTemplateType.WELCOME,
            "support_followup": EmailTemplateType.SUPPORT_FOLLOWUP,
            "high_value_checkin": EmailTemplateType.HIGH_VALUE_CHECKIN,
        }
        template_type = purpose_map.get(purpose_str, EmailTemplateType.CUSTOM)
        
        emails_generated = []
        
        for cid in customer_ids:
            customer = db.query(Customer).filter(Customer.customer_id == cid).first()
            if not customer:
                logger.warning(f"Customer {cid} not found, skipping email generation")
                continue
            
            if not customer.email:
                logger.warning(f"Customer {cid} has no email address, skipping")
                continue
            
            additional_context = {}
            if include_discount and discount_details:
                additional_context["discount_offer"] = discount_details
            if custom_purpose:
                additional_context["custom_purpose"] = custom_purpose
            
            try:
                draft = email_service.generate_email(
                    customer=customer,
                    template_type=template_type,
                    tone=tone,
                    additional_context=additional_context if additional_context else None,
                )
                
                emails_generated.append({
                    "customer_id": customer.customer_id,
                    "customer_name": customer.name,
                    "customer_email": customer.email,
                    "subject": draft.subject,
                    "body": draft.body,
                    "html_body": draft.html_body,
                    "template_type": draft.template_type.value,
                    "personalization_notes": f"Generated using {draft.template_type.value} template",
                })
            except Exception as e:
                logger.error(f"Failed to generate email for customer {cid}: {e}")
                emails_generated.append({
                    "customer_id": customer.customer_id,
                    "customer_name": customer.name,
                    "customer_email": customer.email,
                    "error": str(e),
                })
        
        return ToolResult(
            success=True,
            data={
                "emails": emails_generated,
                "count": len(emails_generated),
                "purpose": purpose_str,
                "tone": tone,
            },
        )


class SendEmailTool(BaseTool):
    """Tool for sending emails with approval workflow integration."""
    
    def _get_description(self) -> str:
        return "Send emails to customers with approval workflow. Requires approval for external email sending."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="send_email",
            description=self._get_description(),
            parameters=[
                ToolParameter("emails", "array", "List of email objects with customer_id, subject, body, html_body", required=True),
                ToolParameter("auto_approve", "boolean", "Auto-approve if approval not required", required=False, default=False),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        email_service = create_customer_email_service()
        approval_service = create_approval_service(db)
        
        emails_data = parameters.get("emails", [])
        if not emails_data:
            return ToolResult(success=False, error="No emails provided")
        
        auto_approve = parameters.get("auto_approve", context.variables.get("auto_approve", False))
        
        # Convert emails_data to EmailDraft objects
        from src.services.customer_email import EmailDraft, EmailTemplateType
        drafts = []
        for email_data in emails_data:
            # Validate required fields
            if not email_data.get("customer_email"):
                return ToolResult(success=False, error="Missing customer_email in email data")
            if not email_data.get("subject"):
                return ToolResult(success=False, error="Missing subject in email data")
            if not email_data.get("body"):
                return ToolResult(success=False, error="Missing body in email data")
            
            draft = EmailDraft(
                customer_id=email_data.get("customer_id"),
                customer_email=email_data["customer_email"],
                customer_name=email_data.get("customer_name", "Valued Customer"),
                subject=email_data["subject"],
                body=email_data["body"],
                html_body=email_data.get("html_body"),
                template_type=EmailTemplateType(email_data.get("template_type", "custom")),
            )
            drafts.append(draft)
        
        # Check if we have an existing approval
        approval_id = parameters.get("approval_id")
        
        if approval_id:
            # Check approval status
            approval_service = create_approval_service(db)
            approval = approval_service.get_approval(approval_id)
            if not approval:
                return ToolResult(success=False, error=f"Approval {approval_id} not found")
            
            if approval.status != ApprovalStatus.APPROVED:
                return ToolResult(success=False, error=f"Approval not granted: {approval.status.value}")
            
            # Approved - send emails
            result = email_service.send_bulk_emails(drafts, require_approval=False)
            return ToolResult(
                success=result.success,
                data={
                    "emails_sent": result.details.get("count", 0) if result.details else 0,
                    "results": result.details.get("results", []) if result.details else [],
                    "message": result.message,
                },
            )
        
        # No approval yet - request one
        if auto_approve:
            # Auto-approve - send immediately
            result = email_service.send_bulk_emails(drafts, require_approval=False)
            return ToolResult(
                success=result.success,
                data={
                    "emails_sent": result.details.get("count", 0) if result.details else 0,
                    "results": result.details.get("results", []) if result.details else [],
                    "status": "auto_approved",
                    "message": result.message,
                },
            )
        
        # Request approval
        approval_service = create_approval_service(db)
        approval = approval_service.create_approval(
            approval_type="send_email",
            title=f"Send {len(drafts)} email(s)",
            description=f"Request to send {len(drafts)} email(s) to customers",
            content={"drafts": [
                {
                    "customer_id": d.customer_id,
                    "customer_email": d.customer_email,
                    "customer_name": d.customer_name,
                    "subject": d.subject,
                }
                for d in drafts
            ]},
            workflow_execution_id=context.variables.get("workflow_execution_id"),
            requested_by=context.variables.get("user", "system"),
        )
        
        return ToolResult(
            success=True,
            data={
                "approval_id": approval.id,
                "status": "pending_approval",
                "message": f"Approval requested for sending {len(drafts)} email(s)",
            },
        )


class CreateReminderTool(BaseTool):
    """Tool for creating reminders for customer follow-ups."""
    
    def _get_description(self) -> str:
        return "Create reminders for customer follow-ups with trigger time and frequency."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="create_reminder",
            description=self._get_description(),
            parameters=[
                ToolParameter("customer_ids", "array", "List of customer IDs to create reminders for", required=True),
                ToolParameter("title", "string", "Reminder title", required=True),
                ToolParameter("description", "string", "Reminder description", required=False, default=""),
                ToolParameter("trigger_time", "string", "Trigger time in ISO format (YYYY-MM-DDTHH:MM:SS)", required=True),
                ToolParameter("frequency", "string", "Reminder frequency", required=False, default="once",
                             enum=["once", "daily", "weekly", "monthly", "yearly"]),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        repo = ReminderRepository(db)
        
        customer_ids = parameters.get("customer_ids", [])
        if not customer_ids:
            if not context.selected_customers:
                return ToolResult(success=False, error="No customers selected for reminder creation")
            customer_ids = [c["customer_id"] for c in context.selected_customers]
        
        try:
            trigger_time = datetime.fromisoformat(parameters["trigger_time"])
        except ValueError:
            return ToolResult(success=False, error="Invalid trigger_time format. Use ISO format YYYY-MM-DDTHH:MM:SS")
        
        if trigger_time < datetime.now():
            return ToolResult(success=False, error="Trigger time must be in the future")
        
        reminders_created = []
        for cid in customer_ids:
            customer = db.query(Customer).filter(Customer.customer_id == cid).first()
            if not customer:
                logger.warning(f"Customer {cid} not found, skipping reminder creation")
                continue
            
            reminder = Reminder(
                customer_id=customer.id,
                title=parameters["title"],
                description=parameters.get("description", ""),
                trigger_time=trigger_time,
                frequency=parameters.get("frequency", "once"),
                enabled=True,
            )
            repo.create(reminder)
            reminders_created.append({
                "reminder_id": reminder.id,
                "customer_id": cid,
                "title": reminder.title,
                "trigger_time": reminder.trigger_time.isoformat(),
            })
        
        db.commit()
        
        return ToolResult(
            success=True,
            data={
                "reminders_created": reminders_created,
                "count": len(reminders_created),
            },
        )


class ScheduleWorkflowTool(BaseTool):
    """Tool for scheduling recurring workflows."""
    
    def _get_description(self) -> str:
        return "Schedule a workflow to run periodically (daily, weekly, monthly) with specified parameters."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="schedule_workflow",
            description=self._get_description(),
            parameters=[
                ToolParameter("workflow_name", "string", "Name of the workflow to schedule", required=True),
                ToolParameter("schedule_type", "string", "Schedule type", required=True,
                             enum=["daily", "weekly", "monthly", "cron"]),
                ToolParameter("schedule_config", "object", "Schedule configuration (e.g., time, day_of_week, cron_expression)", required=True),
                ToolParameter("workflow_parameters", "object", "Parameters to pass to the workflow", required=False, default={}),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        # Store scheduled workflow configuration
        # In production, this would integrate with a scheduler like APScheduler
        workflow_name = parameters["workflow_name"]
        schedule_type = parameters["schedule_type"]
        schedule_config = parameters["schedule_config"]
        workflow_parameters = parameters.get("workflow_parameters", {})
        
        # For now, just record the schedule
        return ToolResult(
            success=True,
            data={
                "workflow_name": workflow_name,
                "schedule_type": schedule_type,
                "schedule_config": schedule_config,
                "workflow_parameters": workflow_parameters,
                "status": "scheduled",
            },
        )


class CustomerReportTool(BaseTool):
    """Tool for generating customer reports and analytics."""
    
    def _get_description(self) -> str:
        return "Generate customer reports including segment distribution, engagement metrics, and follow-up summaries."
    
    def _get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="customer_report",
            description=self._get_description(),
            parameters=[
                ToolParameter("report_type", "string", "Type of report to generate", required=True,
                             enum=["dashboard", "segment_distribution", "follow_up_summary", "payment_status", "engagement_metrics", "custom"]),
                ToolParameter("filters", "object", "Filters to apply to the report", required=False, default={}),
            ]
        )
    
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        db = next(get_db())
        repo = CustomerRepository(db)
        
        report_type = parameters["report_type"]
        filters = parameters.get("filters", {})
        
        if report_type == "dashboard":
            stats = repo.get_dashboard_stats()
            return ToolResult(success=True, data={"report_type": "dashboard", "data": stats})
        
        elif report_type == "segment_distribution":
            dist = repo.get_segment_distribution()
            return ToolResult(success=True, data={"report_type": "segment_distribution", "data": dist})
        
        elif report_type == "status_distribution":
            dist = repo.get_status_distribution()
            return ToolResult(success=True, data={"report_type": "status_distribution", "data": dist})
        
        elif report_type == "follow_up_summary":
            task_repo = TaskRepository(db)
            pending = task_repo.get_pending_tasks()
            overdue = task_repo.get_overdue_tasks()
            return ToolResult(
                success=True,
                data={
                    "report_type": "follow_up_summary",
                    "data": {
                        "pending_tasks": len(pending),
                        "overdue_tasks": len(overdue),
                        "pending_task_details": [
                            {"id": t.id, "title": t.title, "customer_id": t.customer_id, "due_date": t.due_date.isoformat() if t.due_date else None}
                            for t in pending[:20]
                        ],
                    },
                }
            )
        
        else:
            return ToolResult(success=False, error=f"Unknown report type: {report_type}")


def register_all_tools() -> None:
    """Register all available tools in the global registry."""
    tools = [
        CustomerSearchTool(),
        CustomerAnalysisTool(),
        CreateTaskTool(),
        GenerateEmailTool(),
        SendEmailTool(),
        CreateReminderTool(),
        ScheduleWorkflowTool(),
        CustomerReportTool(),
    ]
    
    for tool in tools:
        tool_registry.register(tool)
    
    logger.info(f"Registered {len(tools)} tools: {tool_registry.get_tool_names()}")


# Register tools on module import
register_all_tools()