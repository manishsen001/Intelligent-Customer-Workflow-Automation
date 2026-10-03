"""Database models for Customer Workflow Automation System."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class CustomerStatus(enum.Enum):
    """Customer status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PROSPECT = "prospect"
    CHURNED = "churned"
    ON_HOLD = "on_hold"


class CustomerSegment(enum.Enum):
    """Customer segment enumeration."""
    NEW_CUSTOMER = "new_customer"
    ACTIVE_CUSTOMER = "active_customer"
    LOYAL_CUSTOMER = "loyal_customer"
    AT_RISK_CUSTOMER = "at_risk_customer"
    INACTIVE_CUSTOMER = "inactive_customer"
    HIGH_VALUE_CUSTOMER = "high_value_customer"
    POTENTIAL_LEAD = "potential_lead"
    PAYMENT_RISK = "payment_risk"


class CustomerType(enum.Enum):
    """Customer type enumeration."""
    INDIVIDUAL = "individual"
    COMPANY = "company"
    ENTERPRISE = "enterprise"
    SMB = "smb"


class PaymentStatus(enum.Enum):
    """Payment status enumeration."""
    CURRENT = "current"
    OVERDUE = "overdue"
    PARTIAL = "partial"
    PAID = "paid"
    DISPUTED = "disputed"


class SupportStatus(enum.Enum):
    """Support status enumeration."""
    NONE = "none"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class InteractionType(enum.Enum):
    """Interaction type enumeration."""
    EMAIL = "email"
    CALL = "call"
    MEETING = "meeting"
    TASK = "task"
    REMINDER = "reminder"
    PURCHASE = "purchase"
    SUPPORT = "support"
    CAMPAIGN = "campaign"
    NOTE = "note"
    WORKFLOW = "workflow"


class TaskStatus(enum.Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"


class WorkflowStatus(enum.Enum):
    """Workflow execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"


class ApprovalStatus(enum.Enum):
    """Approval status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class CampaignStatus(enum.Enum):
    """Campaign status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FollowUpStatus(enum.Enum):
    """Follow-up status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class ScheduledWorkflowStatus(enum.Enum):
    """Scheduled workflow status enumeration."""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    COMPLETED = "completed"


class ScheduledWorkflowFrequency(enum.Enum):
    """Scheduled workflow frequency enumeration."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"


class TicketType(enum.Enum):
    """Support ticket type enumeration."""
    INCIDENT = "incident"
    REQUEST = "request"
    PROBLEM = "problem"
    QUESTION = "question"


class TicketPriority(enum.Enum):
    """Support ticket priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(enum.Enum):
    """Support ticket status enumeration."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_CUSTOMER = "pending_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketQueue(enum.Enum):
    """Support ticket queue/department enumeration."""
    TECHNICAL_SUPPORT = "technical_support"
    BILLING_PAYMENTS = "billing_payments"
    RETURNS_EXCHANGES = "returns_exchanges"
    SALES_PRESALES = "sales_presales"
    GENERAL = "general"


class Customer(Base):
    """Customer model."""
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_type: Mapped[CustomerType] = mapped_column(Enum(CustomerType), default=CustomerType.INDIVIDUAL)
    lead_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Dates
    signup_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_contact_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Financial
    total_purchase_value: Mapped[float] = mapped_column(default=0.0)
    order_count: Mapped[int] = mapped_column(default=0)
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.CURRENT, index=True)
    outstanding_amount: Mapped[float] = mapped_column(default=0.0)
    
    # Status
    support_status: Mapped[SupportStatus] = mapped_column(Enum(SupportStatus), default=SupportStatus.NONE, index=True)
    customer_status: Mapped[CustomerStatus] = mapped_column(Enum(CustomerStatus), default=CustomerStatus.PROSPECT, index=True)
    customer_segment: Mapped[Optional[CustomerSegment]] = mapped_column(Enum(CustomerSegment), nullable=True, index=True)
    priority: Mapped[int] = mapped_column(default=0, index=True)
    
    # AI Analysis
    engagement_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    value_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    churn_risk: Mapped[Optional[float]] = mapped_column(nullable=True)
    follow_up_priority: Mapped[Optional[float]] = mapped_column(nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_recommendations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    segment_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    interactions: Mapped[list["Interaction"]] = relationship("Interaction", back_populates="customer", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="customer", cascade="all, delete-orphan")
    reminders: Mapped[list["Reminder"]] = relationship("Reminder", back_populates="customer", cascade="all, delete-orphan")
    workflow_executions: Mapped[list["WorkflowExecution"]] = relationship("WorkflowExecution", back_populates="customer", cascade="all, delete-orphan")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="customer", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_customers_email_status", "email", "customer_status"),
        Index("ix_customers_segment_status", "customer_segment", "customer_status"),
        Index("ix_customers_priority_status", "priority", "customer_status"),
    )


class Interaction(Base):
    """Customer interaction history."""
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=False)
    interaction_type: Mapped[InteractionType] = mapped_column(Enum(InteractionType), index=True, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interaction_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)
    
    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="interactions")


class Task(Base):
    """Task model for customer follow-ups and automation."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING, index=True)
    priority: Mapped[int] = mapped_column(default=0, index=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    task_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="tasks")


class Reminder(Base):
    """Reminder model for scheduled follow-ups."""
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_trigger: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    reminder_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="reminders")


class WorkflowExecution(Base):
    """Workflow execution history for observability."""
    __tablename__ = "workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(Enum(WorkflowStatus), default=WorkflowStatus.PENDING, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=True)
    trigger_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_log: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="workflow_executions")


class Approval(Base):
    """Approval model for human-in-the-loop workflows."""
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_execution_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workflow_executions.id", ondelete="SET NULL"), index=True, nullable=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True)
    approval_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True)
    requested_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="approvals")


class Campaign(Base):
    """Campaign model for customer outreach campaigns."""
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_segment: Mapped[Optional[CustomerSegment]] = mapped_column(Enum(CustomerSegment), nullable=True)
    target_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    email_template: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, index=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    schedule_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    total_targeted: Mapped[int] = mapped_column(default=0)
    total_sent: Mapped[int] = mapped_column(default=0)
    total_approved: Mapped[int] = mapped_column(default=0)
    total_rejected: Mapped[int] = mapped_column(default=0)
    total_failed: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class FollowUp(Base):
    """Follow-up model for customer follow-up tracking."""
    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(default=0, index=True)
    status: Mapped[FollowUpStatus] = mapped_column(Enum(FollowUpStatus, values_callable=lambda x: [e.value for e in x]), default=FollowUpStatus.PENDING, index=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    assigned_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    last_contact_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    follow_up_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer")


class ScheduledWorkflow(Base):
    """Scheduled workflow model for recurring workflow execution."""
    __tablename__ = "scheduled_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frequency: Mapped[ScheduledWorkflowFrequency] = mapped_column(Enum(ScheduledWorkflowFrequency), nullable=False)
    schedule_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # time, day_of_week, cron_expression, etc.
    workflow_plan: Mapped[dict] = mapped_column(JSON, nullable=False)  # The workflow plan to execute
    status: Mapped[ScheduledWorkflowStatus] = mapped_column(Enum(ScheduledWorkflowStatus), default=ScheduledWorkflowStatus.ACTIVE, index=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_run_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    run_count: Mapped[int] = mapped_column(default=0)
    max_runs: Mapped[Optional[int]] = mapped_column(nullable=True)
    workflow_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class ScheduledWorkflowExecution(Base):
    """Execution history for scheduled workflows."""
    __tablename__ = "scheduled_workflow_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheduled_workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheduled_workflows.id", ondelete="CASCADE"), index=True, nullable=False)
    execution_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    workflow_plan: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # running, completed, failed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    customers_processed: Mapped[int] = mapped_column(default=0)
    actions_executed: Mapped[int] = mapped_column(default=0)
    errors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EmailLog(Base):
    """Email sending log."""
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), index=True, nullable=True)
    approval_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("approvals.id", ondelete="SET NULL"), index=True, nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    recipients: Mapped[list] = mapped_column(JSON, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    html_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)


class Ticket(Base):
    """Support ticket model."""
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ticket_type: Mapped[TicketType] = mapped_column(Enum(TicketType), default=TicketType.REQUEST, index=True)
    queue: Mapped[TicketQueue] = mapped_column(Enum(TicketQueue), default=TicketQueue.GENERAL, index=True)
    priority: Mapped[TicketPriority] = mapped_column(Enum(TicketPriority), default=TicketPriority.MEDIUM, index=True)
    status: Mapped[TicketStatus] = mapped_column(Enum(TicketStatus), default=TicketStatus.OPEN, index=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "huggingface_dataset"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="tickets")
    
    __table_args__ = (
        Index("ix_tickets_customer_priority", "customer_id", "priority"),
        Index("ix_tickets_customer_status", "customer_id", "status"),
        Index("ix_tickets_queue_priority", "queue", "priority"),
        Index("ix_tickets_created_priority", "created_at", "priority"),
    )


# Add tickets relationship to Customer class
Customer.tickets = relationship("Ticket", back_populates="customer", cascade="all, delete-orphan")