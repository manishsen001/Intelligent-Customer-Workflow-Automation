"""Services package for Customer Workflow Automation System."""

from src.services.customer_data import (
    CustomerDataService,
    IngestionResult,
    ValidationError,
    create_customer_data_service,
)

from src.services.ticket_data import (
    TicketDataService,
    IngestionResult as TicketIngestionResult,
    ValidationError as TicketValidationError,
    create_ticket_data_service,
)

from src.services.customer_intelligence import (
    CustomerIntelligence,
    CustomerAnalysis,
    CustomerScore,
    create_customer_intelligence,
)

from src.services.approval import (
    ApprovalService,
    create_approval_service,
)

from src.services.customer_email import (
    CustomerEmailService,
    EmailDraft,
    EmailResult,
    EmailStatus,
    EmailTemplateType,
    create_customer_email_service,
)

from src.services.follow_up import (
    FollowUpService,
    FollowUpTransitionError,
    create_follow_up_service,
)

from src.services.scheduled_workflow import (
    ScheduledWorkflowEngine,
    create_scheduled_workflow_engine,
)

from src.services.workflow_execution import (
    WorkflowExecutionService,
    create_workflow_execution_service,
)

__all__ = [
    "CustomerDataService",
    "IngestionResult",
    "ValidationError",
    "create_customer_data_service",
    "TicketDataService",
    "TicketIngestionResult",
    "TicketValidationError",
    "create_ticket_data_service",
    "CustomerIntelligence",
    "CustomerAnalysis",
    "CustomerScore",
    "create_customer_intelligence",
    "ApprovalService",
    "create_approval_service",
    "CustomerEmailService",
    "EmailDraft",
    "EmailResult",
    "EmailStatus",
    "EmailTemplateType",
    "create_customer_email_service",
    "FollowUpService",
    "FollowUpTransitionError",
    "create_follow_up_service",
    "ScheduledWorkflowEngine",
    "create_scheduled_workflow_engine",
    "WorkflowExecutionService",
    "create_workflow_execution_service",
]