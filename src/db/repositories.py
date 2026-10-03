"""Repository layer for Customer Workflow Automation System."""

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from src.db.models import (
    Approval,
    ApprovalStatus,
    Campaign,
    CampaignStatus,
    Customer,
    CustomerSegment,
    CustomerStatus,
    EmailLog,
    FollowUp,
    FollowUpStatus,
    Interaction,
    InteractionType,
    PaymentStatus,
    Reminder,
    ScheduledWorkflow,
    ScheduledWorkflowExecution,
    ScheduledWorkflowFrequency,
    ScheduledWorkflowStatus,
    SupportStatus,
    Task,
    TaskStatus,
    Ticket,
    TicketPriority,
    TicketQueue,
    TicketStatus,
    TicketType,
    WorkflowExecution,
    WorkflowStatus,
)


class CustomerRepository:
    """Repository for customer data access."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, customer: Customer) -> Customer:
        """Create a new customer."""
        self.session.add(customer)
        self.session.flush()
        self.session.refresh(customer)
        return customer
    
    def get_by_id(self, customer_id: int) -> Optional[Customer]:
        """Get customer by internal ID."""
        return self.session.get(Customer, customer_id)
    
    def get_by_customer_id(self, customer_id: str) -> Optional[Customer]:
        """Get customer by customer_id field."""
        stmt = select(Customer).where(Customer.customer_id == customer_id)
        return self.session.execute(stmt).scalar_one_or_none()
    
    def get_by_email(self, email: str) -> Optional[Customer]:
        """Get customer by email."""
        stmt = select(Customer).where(Customer.email == email)
        return self.session.execute(stmt).scalar_one_or_none()
    
    def list_customers(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict] = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
    ) -> list[Customer]:
        """List customers with filtering and sorting."""
        stmt = select(Customer)
        
        if filters:
            conditions = []
            if filters.get("segment"):
                conditions.append(Customer.customer_segment == filters["segment"])
            if filters.get("status"):
                conditions.append(Customer.customer_status == filters["status"])
            if filters.get("payment_status"):
                conditions.append(Customer.payment_status == filters["payment_status"])
            if filters.get("support_status"):
                conditions.append(Customer.support_status == filters["support_status"])
            if filters.get("search"):
                search = f"%{filters['search']}%"
                conditions.append(
                    or_(
                        Customer.name.ilike(search),
                        Customer.email.ilike(search),
                        Customer.customer_id.ilike(search),
                        Customer.company.ilike(search),
                    )
                )
            if filters.get("min_priority") is not None:
                conditions.append(Customer.priority >= filters["min_priority"])
            if filters.get("has_outstanding"):
                conditions.append(Customer.outstanding_amount > 0)
            if conditions:
                stmt = stmt.where(and_(*conditions))
        
        # Sorting
        sort_column = getattr(Customer, sort_by, Customer.created_at)
        if sort_desc:
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(sort_column)
        
        stmt = stmt.offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def count_customers(self, filters: Optional[dict] = None) -> int:
        """Count customers with filters."""
        stmt = select(func.count(Customer.id))
        
        if filters:
            conditions = []
            if filters.get("segment"):
                conditions.append(Customer.customer_segment == filters["segment"])
            if filters.get("status"):
                conditions.append(Customer.customer_status == filters["status"])
            if filters.get("payment_status"):
                conditions.append(Customer.payment_status == filters["payment_status"])
            if filters.get("support_status"):
                conditions.append(Customer.support_status == filters["support_status"])
            if filters.get("search"):
                search = f"%{filters['search']}%"
                conditions.append(
                    or_(
                        Customer.name.ilike(search),
                        Customer.email.ilike(search),
                        Customer.customer_id.ilike(search),
                        Customer.company.ilike(search),
                    )
                )
            if filters.get("min_priority") is not None:
                conditions.append(Customer.priority >= filters["min_priority"])
            if filters.get("has_outstanding"):
                conditions.append(Customer.outstanding_amount > 0)
            if conditions:
                stmt = stmt.where(and_(*conditions))
        
        return self.session.execute(stmt).scalar() or 0
    
    def update(self, customer: Customer) -> Customer:
        """Update customer."""
        customer.updated_at = datetime.now()
        self.session.flush()
        self.session.refresh(customer)
        return customer
    
    def delete(self, customer_id: int) -> bool:
        """Delete customer by ID."""
        customer = self.get_by_id(customer_id)
        if customer:
            self.session.delete(customer)
            return True
        return False
    
    def get_dashboard_stats(self) -> dict[str, Any]:
        """Get dashboard statistics."""
        total = self.session.execute(select(func.count(Customer.id))).scalar() or 0
        
        active = self.session.execute(
            select(func.count(Customer.id)).where(Customer.customer_status == CustomerStatus.ACTIVE)
        ).scalar() or 0
        
        inactive = self.session.execute(
            select(func.count(Customer.id)).where(Customer.customer_status == CustomerStatus.INACTIVE)
        ).scalar() or 0
        
        high_value = self.session.execute(
            select(func.count(Customer.id)).where(Customer.customer_segment == CustomerSegment.HIGH_VALUE_CUSTOMER)
        ).scalar() or 0
        
        at_risk = self.session.execute(
            select(func.count(Customer.id)).where(Customer.customer_segment == CustomerSegment.AT_RISK_CUSTOMER)
        ).scalar() or 0
        
        payment_risk = self.session.execute(
            select(func.count(Customer.id)).where(Customer.customer_segment == CustomerSegment.PAYMENT_RISK)
        ).scalar() or 0
        
        overdue_payments = self.session.execute(
            select(func.count(Customer.id)).where(
                and_(
                    Customer.payment_status == PaymentStatus.OVERDUE,
                    Customer.outstanding_amount > 0
                )
            )
        ).scalar() or 0
        
        return {
            "total_customers": total,
            "active_customers": active,
            "inactive_customers": inactive,
            "high_value_customers": high_value,
            "at_risk_customers": at_risk,
            "payment_risk_customers": payment_risk,
            "overdue_payments": overdue_payments,
        }
    
    def get_segment_distribution(self) -> dict[str, int]:
        """Get customer distribution by segment."""
        stmt = select(
            Customer.customer_segment,
            func.count(Customer.id)
        ).group_by(Customer.customer_segment)
        results = self.session.execute(stmt).all()
        return {seg.value if seg else "unassigned": count for seg, count in results}
    
    def get_status_distribution(self) -> dict[str, int]:
        """Get customer distribution by status."""
        stmt = select(
            Customer.customer_status,
            func.count(Customer.id)
        ).group_by(Customer.customer_status)
        results = self.session.execute(stmt).all()
        return {status.value: count for status, count in results}


class InteractionRepository:
    """Repository for interaction history."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, interaction: Interaction) -> Interaction:
        """Create an interaction."""
        self.session.add(interaction)
        self.session.flush()
        self.session.refresh(interaction)
        return interaction
    
    def get_customer_interactions(
        self,
        customer_id: int,
        limit: int = 50,
        interaction_type: Optional[InteractionType] = None,
    ) -> list[Interaction]:
        """Get interactions for a customer."""
        stmt = select(Interaction).where(Interaction.customer_id == customer_id)
        
        if interaction_type:
            stmt = stmt.where(Interaction.interaction_type == interaction_type)
        
        stmt = stmt.order_by(desc(Interaction.created_at)).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def count_customer_interactions(
        self,
        customer_id: int,
        interaction_type: Optional[InteractionType] = None,
    ) -> int:
        """Count interactions for a customer."""
        stmt = select(func.count(Interaction.id)).where(Interaction.customer_id == customer_id)
        
        if interaction_type:
            stmt = stmt.where(Interaction.interaction_type == interaction_type)
        
        return self.session.execute(stmt).scalar() or 0


class TaskRepository:
    """Repository for tasks."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, task: Task) -> Task:
        """Create a task."""
        self.session.add(task)
        self.session.flush()
        self.session.refresh(task)
        return task
    
    def get_by_id(self, task_id: int) -> Optional[Task]:
        """Get task by ID."""
        return self.session.get(Task, task_id)
    
    def list_tasks(
        self,
        customer_id: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Task]:
        """List tasks with filters."""
        stmt = select(Task)
        
        if customer_id:
            stmt = stmt.where(Task.customer_id == customer_id)
        if status:
            stmt = stmt.where(Task.status == status)
        
        stmt = stmt.order_by(desc(Task.priority), Task.due_date).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def update(self, task: Task) -> Task:
        """Update task."""
        task.updated_at = datetime.now()
        self.session.flush()
        self.session.refresh(task)
        return task
    
    def get_pending_tasks(self, customer_id: Optional[int] = None) -> list[Task]:
        """Get pending tasks."""
        return self.list_tasks(customer_id=customer_id, status=TaskStatus.PENDING)
    
    def get_overdue_tasks(self, customer_id: Optional[int] = None) -> list[Task]:
        """Get overdue tasks."""
        stmt = select(Task).where(
            and_(
                Task.due_date < datetime.now(),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            )
        )
        if customer_id:
            stmt = stmt.where(Task.customer_id == customer_id)
        return list(self.session.execute(stmt).scalars().all())


class ReminderRepository:
    """Repository for reminders."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, reminder: Reminder) -> Reminder:
        """Create a reminder."""
        self.session.add(reminder)
        self.session.flush()
        self.session.refresh(reminder)
        return reminder
    
    def get_by_id(self, reminder_id: int) -> Optional[Reminder]:
        """Get reminder by ID."""
        return self.session.get(Reminder, reminder_id)
    
    def list_reminders(
        self,
        customer_id: Optional[int] = None,
        enabled_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Reminder]:
        """List reminders with filters."""
        stmt = select(Reminder)
        
        if customer_id:
            stmt = stmt.where(Reminder.customer_id == customer_id)
        if enabled_only:
            stmt = stmt.where(Reminder.enabled == True)
        
        stmt = stmt.order_by(Reminder.next_trigger).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def get_due_reminders(self) -> list[Reminder]:
        """Get reminders that are due."""
        stmt = select(Reminder).where(
            and_(
                Reminder.enabled == True,
                Reminder.next_trigger != None,
                Reminder.next_trigger <= datetime.now(),
            )
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def update(self, reminder: Reminder) -> Reminder:
        """Update reminder."""
        reminder.updated_at = datetime.now()
        self.session.flush()
        self.session.refresh(reminder)
        return reminder
    
    def delete(self, reminder_id: int) -> bool:
        """Delete reminder by ID."""
        reminder = self.get_by_id(reminder_id)
        if reminder:
            self.session.delete(reminder)
            return True
        return False


class WorkflowExecutionRepository:
    """Repository for workflow execution history."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Create a workflow execution record."""
        self.session.add(execution)
        self.session.flush()
        self.session.refresh(execution)
        return execution
    
    def get_by_id(self, execution_id: int) -> Optional[WorkflowExecution]:
        """Get execution by ID."""
        return self.session.get(WorkflowExecution, execution_id)
    
    def get_by_workflow_id(self, workflow_id: str) -> Optional[WorkflowExecution]:
        """Get latest execution by workflow ID."""
        stmt = select(WorkflowExecution).where(
            WorkflowExecution.workflow_id == workflow_id
        ).order_by(desc(WorkflowExecution.started_at)).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()
    
    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[WorkflowExecution]:
        """List workflow executions."""
        stmt = select(WorkflowExecution)
        
        if workflow_id:
            stmt = stmt.where(WorkflowExecution.workflow_id == workflow_id)
        if customer_id:
            stmt = stmt.where(WorkflowExecution.customer_id == customer_id)
        if status:
            from src.db.models import WorkflowStatus
            stmt = stmt.where(WorkflowExecution.status == WorkflowStatus(status))
        
        stmt = stmt.order_by(desc(WorkflowExecution.started_at)).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def update(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Update workflow execution."""
        self.session.flush()
        self.session.refresh(execution)
        return execution


class ApprovalRepository:
    """Repository for approvals."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, approval: Approval) -> Approval:
        """Create an approval request."""
        self.session.add(approval)
        self.session.flush()
        self.session.refresh(approval)
        return approval
    
    def get_by_id(self, approval_id: int) -> Optional[Approval]:
        """Get approval by ID."""
        return self.session.get(Approval, approval_id)
    
    def list_approvals(
        self,
        status: Optional[ApprovalStatus] = None,
        customer_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Approval]:
        """List approvals with filters."""
        stmt = select(Approval)
        
        if status:
            stmt = stmt.where(Approval.status == status)
        if customer_id:
            stmt = stmt.where(Approval.customer_id == customer_id)
        
        stmt = stmt.order_by(desc(Approval.created_at)).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def get_pending_approvals(self, customer_id: Optional[int] = None) -> list[Approval]:
        """Get pending approvals."""
        return self.list_approvals(status=ApprovalStatus.PENDING, customer_id=customer_id)
    
    def update(self, approval: Approval) -> Approval:
        """Update approval."""
        approval.updated_at = datetime.now()
        self.session.flush()
        self.session.refresh(approval)
        return approval


class CampaignRepository:
    """Repository for campaigns."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, campaign: Campaign) -> Campaign:
        """Create a campaign."""
        self.session.add(campaign)
        self.session.flush()
        self.session.refresh(campaign)
        return campaign
    
    def get_by_id(self, campaign_id: int) -> Optional[Campaign]:
        """Get campaign by ID."""
        return self.session.get(Campaign, campaign_id)
    
    def list_campaigns(
        self,
        status: Optional[CampaignStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Campaign]:
        """List campaigns."""
        stmt = select(Campaign)
        
        if status:
            stmt = stmt.where(Campaign.status == status)
        
        stmt = stmt.order_by(desc(Campaign.created_at)).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def update(self, campaign: Campaign) -> Campaign:
        """Update campaign."""
        campaign.updated_at = datetime.now()
        self.session.flush()
        self.session.refresh(campaign)
        return campaign


class EmailLogRepository:
    """Repository for email logs."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, email_log: EmailLog) -> EmailLog:
        """Create an email log."""
        self.session.add(email_log)
        self.session.flush()
        self.session.refresh(email_log)
        return email_log
    
    def list_logs(
        self,
        customer_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[EmailLog]:
        """List email logs."""
        stmt = select(EmailLog)
        
        if customer_id:
            stmt = stmt.where(EmailLog.customer_id == customer_id)
        if campaign_id:
            stmt = stmt.where(EmailLog.campaign_id == campaign_id)
        if status:
            stmt = stmt.where(EmailLog.status == status)
        
        stmt = stmt.order_by(desc(EmailLog.created_at)).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())


def list_logs(
        self,
        customer_id: Optional[int] = None,
        campaign_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[EmailLog]:
        """List email logs."""
        stmt = select(EmailLog)
        
        if customer_id:
            stmt = stmt.where(EmailLog.customer_id == customer_id)
        if campaign_id:
            stmt = stmt.where(EmailLog.campaign_id == campaign_id)
        if status:
            stmt = stmt.where(EmailLog.status == status)
        
        stmt = stmt.order_by(desc(EmailLog.created_at)).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())


class TicketRepository:
    """Repository for support tickets."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, ticket: Ticket) -> Ticket:
        """Create a new ticket."""
        self.session.add(ticket)
        self.session.flush()
        self.session.refresh(ticket)
        return ticket
    
    def get_by_id(self, ticket_id: int) -> Optional[Ticket]:
        """Get ticket by internal ID."""
        return self.session.get(Ticket, ticket_id)
    
    def get_by_ticket_id(self, ticket_id: str) -> Optional[Ticket]:
        """Get ticket by ticket_id field."""
        stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
        return self.session.execute(stmt).scalar_one_or_none()
    
    def list_tickets(
        self,
        customer_id: Optional[int] = None,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        queue: Optional[TicketQueue] = None,
        ticket_type: Optional[TicketType] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Ticket]:
        """List tickets with filtering."""
        stmt = select(Ticket)
        
        if customer_id:
            stmt = stmt.where(Ticket.customer_id == customer_id)
        if status:
            stmt = stmt.where(Ticket.status == status)
        if priority:
            stmt = stmt.where(Ticket.priority == priority)
        if queue:
            stmt = stmt.where(Ticket.queue == queue)
        if ticket_type:
            stmt = stmt.where(Ticket.ticket_type == ticket_type)
        
        stmt = stmt.order_by(desc(Ticket.created_at)).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def count_tickets(
        self,
        customer_id: Optional[int] = None,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
    ) -> int:
        """Count tickets with filters."""
        stmt = select(func.count(Ticket.id))
        
        if customer_id:
            stmt = stmt.where(Ticket.customer_id == customer_id)
        if status:
            stmt = stmt.where(Ticket.status == status)
        if priority:
            stmt = stmt.where(Ticket.priority == priority)
        
        return self.session.execute(stmt).scalar() or 0
    
    def get_tickets_by_customer(self, customer_id: int, limit: int = 50) -> list[Ticket]:
        """Get tickets for a specific customer."""
        return self.list_tickets(customer_id=customer_id, limit=limit)
    
    def get_open_tickets(self, customer_id: Optional[int] = None) -> list[Ticket]:
        """Get open tickets."""
        return self.list_tickets(customer_id=customer_id, status=TicketStatus.OPEN)
    
    def get_high_priority_tickets(self, customer_id: Optional[int] = None) -> list[Ticket]:
        """Get high and critical priority tickets."""
        stmt = select(Ticket).where(
            Ticket.priority.in_([TicketPriority.HIGH, TicketPriority.CRITICAL])
        )
        if customer_id:
            stmt = stmt.where(Ticket.customer_id == customer_id)
        stmt = stmt.order_by(desc(Ticket.created_at))
        return list(self.session.execute(stmt).scalars().all())
    
    def update(self, ticket: Ticket) -> Ticket:
        """Update ticket."""
        ticket.updated_at = datetime.now()
        self.session.flush()
        self.session.refresh(ticket)
        return ticket
    
    def resolve_ticket(self, ticket_id: int, resolution: str) -> Optional[Ticket]:
        """Mark ticket as resolved with resolution text."""
        ticket = self.get_by_id(ticket_id)
        if ticket:
            ticket.status = TicketStatus.RESOLVED
            ticket.resolution = resolution
            ticket.resolved_at = datetime.now()
            ticket.updated_at = datetime.now()
            self.session.flush()
            self.session.refresh(ticket)
        return ticket
    
    def close_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """Close a resolved ticket."""
        ticket = self.get_by_id(ticket_id)
        if ticket and ticket.status == TicketStatus.RESOLVED:
            ticket.status = TicketStatus.CLOSED
            ticket.updated_at = datetime.now()
            self.session.flush()
            self.session.refresh(ticket)
        return ticket
    
    def get_queue_stats(self) -> dict[str, int]:
        """Get ticket count by queue."""
        stmt = select(Ticket.queue, func.count(Ticket.id)).group_by(Ticket.queue)
        results = self.session.execute(stmt).all()
        return {queue.value: count for queue, count in results}
    
    def get_priority_stats(self) -> dict[str, int]:
        """Get ticket count by priority."""
        stmt = select(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority)
        results = self.session.execute(stmt).all()
        return {priority.value: count for priority, count in results}
    
    def get_status_stats(self) -> dict[str, int]:
        """Get ticket count by status."""
        stmt = select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
        results = self.session.execute(stmt).all()
        return {status.value: count for status, count in results}


class FollowUpRepository:
    """Repository for follow-ups."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, follow_up: FollowUp) -> FollowUp:
        """Create a follow-up."""
        self.session.add(follow_up)
        self.session.flush()
        self.session.refresh(follow_up)
        return follow_up
    
    def get_by_id(self, follow_up_id: int) -> Optional[FollowUp]:
        """Get follow-up by ID."""
        return self.session.get(FollowUp, follow_up_id)
    
    def list_follow_ups(
        self,
        customer_id: Optional[int] = None,
        status: Optional[FollowUpStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FollowUp]:
        """List follow-ups with filters."""
        stmt = select(FollowUp)
        
        if customer_id:
            stmt = stmt.where(FollowUp.customer_id == customer_id)
        if status:
            stmt = stmt.where(FollowUp.status == status)
        
        stmt = stmt.order_by(desc(FollowUp.priority), FollowUp.due_date).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def get_overdue_follow_ups(self) -> list[FollowUp]:
        """Get overdue follow-ups."""
        stmt = select(FollowUp).where(
            and_(
                FollowUp.due_date < datetime.now(),
                FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS]),
            )
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def get_todays_follow_ups(self) -> list[FollowUp]:
        """Get follow-ups due today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)
        stmt = select(FollowUp).where(
            and_(
                FollowUp.due_date >= today_start,
                FollowUp.due_date <= today_end,
                FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS]),
            )
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def get_upcoming_follow_ups(self, days: int = 7) -> list[FollowUp]:
        """Get upcoming follow-ups within specified days."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        future_end = today_start + timedelta(days=days)
        stmt = select(FollowUp).where(
            and_(
                FollowUp.due_date >= today_start,
                FollowUp.due_date <= future_end,
                FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS]),
            )
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def get_high_priority_follow_ups(self, min_priority: int = 50) -> list[FollowUp]:
        """Get high-priority follow-ups."""
        stmt = select(FollowUp).where(
            and_(
                FollowUp.priority >= min_priority,
                FollowUp.status.in_([FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS]),
            )
        ).order_by(desc(FollowUp.priority))
        return list(self.session.execute(stmt).scalars().all())
    
    def update(self, follow_up: FollowUp) -> FollowUp:
        """Update follow-up."""
        follow_up.updated_at = datetime.now()
        self.session.flush()
        self.session.refresh(follow_up)
        return follow_up
    
    def delete(self, follow_up_id: int) -> bool:
        """Delete follow-up by ID."""
        follow_up = self.get_by_id(follow_up_id)
        if follow_up:
            self.session.delete(follow_up)
            return True
        return False


class ScheduledWorkflowRepository:
    """Repository for scheduled workflows."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, workflow: ScheduledWorkflow) -> ScheduledWorkflow:
        """Create a scheduled workflow."""
        self.session.add(workflow)
        self.session.flush()
        self.session.refresh(workflow)
        return workflow
    
    def get_by_id(self, workflow_id: int) -> Optional[ScheduledWorkflow]:
        """Get scheduled workflow by ID."""
        return self.session.get(ScheduledWorkflow, workflow_id)
    
    def get_by_workflow_id(self, workflow_id: str) -> Optional[ScheduledWorkflow]:
        """Get scheduled workflow by workflow_id field."""
        stmt = select(ScheduledWorkflow).where(ScheduledWorkflow.workflow_id == workflow_id)
        return self.session.execute(stmt).scalar_one_or_none()
    
    def list_workflows(
        self,
        status: Optional[ScheduledWorkflowStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ScheduledWorkflow]:
        """List scheduled workflows."""
        stmt = select(ScheduledWorkflow)
        
        if status:
            stmt = stmt.where(ScheduledWorkflow.status == status)
        
        stmt = stmt.order_by(desc(ScheduledWorkflow.created_at)).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def get_due_workflows(self) -> list[ScheduledWorkflow]:
        """Get workflows that are due to run."""
        stmt = select(ScheduledWorkflow).where(
            and_(
                ScheduledWorkflow.status == ScheduledWorkflowStatus.ACTIVE,
                ScheduledWorkflow.next_run != None,
                ScheduledWorkflow.next_run <= datetime.now(),
            )
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def update(self, workflow: ScheduledWorkflow) -> ScheduledWorkflow:
        """Update scheduled workflow."""
        workflow.updated_at = datetime.now()
        self.session.flush()
        self.session.refresh(workflow)
        return workflow
    
    def update_next_run(self, workflow_id: int, next_run: datetime, status: str = None) -> bool:
        """Update next run time for a workflow."""
        workflow = self.get_by_id(workflow_id)
        if workflow:
            workflow.next_run = next_run
            if status:
                workflow.status = ScheduledWorkflowStatus(status)
            workflow.updated_at = datetime.now()
            workflow.run_count += 1
            self.session.flush()
            return True
        return False
    
    def update_last_run(self, workflow_id: int, last_run: datetime, status: str, result: dict = None) -> bool:
        """Update last run info for a workflow."""
        workflow = self.get_by_id(workflow_id)
        if workflow:
            workflow.last_run = last_run
            workflow.last_run_status = status
            workflow.last_run_result = result
            workflow.updated_at = datetime.now()
            self.session.flush()
            return True
        return False
    
    def delete(self, workflow_id: int) -> bool:
        """Delete scheduled workflow by ID."""
        workflow = self.get_by_id(workflow_id)
        if workflow:
            self.session.delete(workflow)
            return True
        return False


class ScheduledWorkflowExecutionRepository:
    """Repository for scheduled workflow executions."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, execution: ScheduledWorkflowExecution) -> ScheduledWorkflowExecution:
        """Create an execution record."""
        self.session.add(execution)
        self.session.flush()
        self.session.refresh(execution)
        return execution
    
    def get_by_id(self, execution_id: int) -> Optional[ScheduledWorkflowExecution]:
        """Get execution by ID."""
        return self.session.get(ScheduledWorkflowExecution, execution_id)
    
    def list_executions(
        self,
        scheduled_workflow_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ScheduledWorkflowExecution]:
        """List executions with filters."""
        stmt = select(ScheduledWorkflowExecution)
        
        if scheduled_workflow_id:
            stmt = stmt.where(ScheduledWorkflowExecution.scheduled_workflow_id == scheduled_workflow_id)
        if status:
            stmt = stmt.where(ScheduledWorkflowExecution.status == status)
        
        stmt = stmt.order_by(desc(ScheduledWorkflowExecution.started_at)).offset(skip).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
    
    def update(self, execution: ScheduledWorkflowExecution) -> ScheduledWorkflowExecution:
        """Update execution."""
        self.session.flush()
        self.session.refresh(execution)
        return execution