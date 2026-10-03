"""Customer-specific models for Intelligent Customer Workflow Automation System."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class CustomerActionType(Enum):
    """Types of customer-specific actions."""
    
    # Customer analysis actions
    ANALYZE_CUSTOMER = "analyze_customer"
    SEGMENT_CUSTOMER = "segment_customer"
    SCORE_CUSTOMER = "score_customer"
    
    # Follow-up actions
    CREATE_FOLLOW_UP = "create_follow_up"
    UPDATE_FOLLOW_UP = "update_follow_up"
    COMPLETE_FOLLOW_UP = "complete_follow_up"
    CANCEL_FOLLOW_UP = "cancel_follow_up"
    GET_OVERDUE_FOLLOW_UPS = "get_overdue_follow_ups"
    GET_UPCOMING_FOLLOW_UPS = "get_upcoming_follow_ups"
    GET_HIGH_PRIORITY_FOLLOW_UPS = "get_high_priority_follow_ups"
    
    # Communication actions
    GENERATE_PERSONALIZED_EMAIL = "generate_personalized_email"
    SEND_PERSONALIZED_EMAIL = "send_personalized_email"
    CREATE_EMAIL_DRAFT = "create_email_draft"
    
    # Task actions
    CREATE_CUSTOMER_TASK = "create_customer_task"
    UPDATE_CUSTOMER_TASK = "update_customer_task"
    COMPLETE_CUSTOMER_TASK = "complete_customer_task"
    
    # Reminder actions
    CREATE_CUSTOMER_REMINDER = "create_customer_reminder"
    
    # Segmentation actions
    SEGMENT_CUSTOMERS = "segment_customers"
    GET_HIGH_VALUE_CUSTOMERS = "get_high_value_customers"
    GET_AT_RISK_CUSTOMERS = "get_at_risk_customers"
    GET_INACTIVE_CUSTOMERS = "get_inactive_customers"
    GET_NEW_CUSTOMERS = "get_new_customers"
    GET_PAYMENT_RISK_CUSTOMERS = "get_payment_risk_customers"
    
    # Reporting actions
    GENERATE_CUSTOMER_REPORT = "generate_customer_report"
    GET_CUSTOMER_DASHBOARD = "get_customer_dashboard"
    
    # Segmentation actions
    UPDATE_CUSTOMER_SEGMENT = "update_customer_segment"
    BULK_SEGMENT_CUSTOMERS = "bulk_segment_customers"


class CustomerFollowUpStatus(Enum):
    """Follow-up status enumeration."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class CustomerPriority(Enum):
    """Customer priority levels."""
    
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class CustomerSegment(Enum):
    """Customer segment enumeration."""
    
    NEW_CUSTOMER = "new_customer"
    ACTIVE_CUSTOMER = "active_customer"
    LOYAL_CUSTOMER = "loyal_customer"
    AT_RISK_CUSTOMER = "at_risk_customer"
    INACTIVE_CUSTOMER = "inactive_customer"
    HIGH_VALUE_CUSTOMER = "high_value_customer"
    POTENTIAL_LEAD = "potential_lead"
    PAYMENT_RISK = "payment_risk"


@dataclass
class CustomerAction:
    """Represents a customer-specific action to be executed."""
    
    action_type: CustomerActionType
    customer_id: Optional[str] = None
    parameters: dict = field(default_factory=dict)
    priority: CustomerPriority = CustomerPriority.MEDIUM
    reasoning: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    action_id: str = field(default_factory=lambda: str(uuid4())[:8])


@dataclass
class CustomerFollowUp:
    """Represents a customer follow-up item."""
    
    customer_id: str
    title: str
    reason: str
    follow_up_id: str = field(default_factory=lambda: str(uuid4())[:8])
    status: CustomerFollowUpStatus = CustomerFollowUpStatus.PENDING
    priority: CustomerPriority = CustomerPriority.MEDIUM
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    next_action: Optional[str] = None
    last_contact_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class CustomerSegmentInfo:
    """Information about a customer segment."""
    
    segment: str
    name: str
    description: str
    criteria: dict
    color: str = "#1f77b4"


# Pre-defined customer segments
CUSTOMER_SEGMENTS = {
    "new_customer": CustomerSegmentInfo(
        segment="new_customer",
        name="New Customer",
        description="Recently acquired customers with limited history",
        criteria={"order_count": {"lte": 1}, "total_purchase_value": {"lt": 1000}},
        color="#2ca02c"
    ),
    "active_customer": CustomerSegmentInfo(
        segment="active_customer",
        name="Active Customer",
        description="Regularly engaged customers with consistent activity",
        criteria={"engagement_score": {"gte": 0.4}, "days_since_contact": {"lte": 30}},
        color="#1f77b4"
    ),
    "loyal_customer": CustomerSegmentInfo(
        segment="loyal_customer",
        name="Loyal Customer",
        description="High-value customers with strong engagement and loyalty",
        criteria={"value_score": {"gte": 0.5}, "engagement_score": {"gte": 0.5}},
        color="#9467bd"
    ),
    "at_risk_customer": CustomerSegmentInfo(
        segment="at_risk_customer",
        name="At-Risk Customer",
        description="Customers showing signs of potential churn",
        criteria={"churn_risk": {"gte": 0.5}},
        color="#ff7f0e"
    ),
    "inactive_customer": CustomerSegmentInfo(
        segment="inactive_customer",
        name="Inactive Customer",
        description="Customers with no recent engagement",
        criteria={"days_since_contact": {"gte": 30}, "customer_status": {"ne": "churned"}},
        color="#d62728"
    ),
    "high_value_customer": CustomerSegmentInfo(
        segment="high_value_customer",
        name="High-Value Customer",
        description="Customers with high lifetime value and frequent purchases",
        criteria={"total_purchase_value": {"gte": 10000}, "order_count": {"gte": 10}},
        color="#e377c2"
    ),
    "potential_lead": CustomerSegmentInfo(
        segment="potential_lead",
        name="Potential Lead",
        description="Prospects with limited or no purchase history",
        criteria={"order_count": {"lte": 1}, "total_purchase_value": {"lt": 1000}},
        color="#8c564b"
    ),
    "payment_risk": CustomerSegmentInfo(
        segment="payment_risk",
        name="Payment Risk",
        description="Customers with overdue payments or significant outstanding amounts",
        criteria={"payment_status": "overdue", "outstanding_amount": {"gt": 1000}},
        color="#bcbd22"
    ),
}


@dataclass
class CustomerInsight:
    """AI-generated insight about a customer."""
    
    customer_id: str
    insight_type: str  # "recommendation", "warning", "opportunity", "trend"
    title: str
    description: str
    confidence: float
    priority: CustomerPriority
    actionable: bool = True
    suggested_actions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CustomerWorkflowContext:
    """Context for customer workflow execution."""
    
    customer_ids: list[str] = field(default_factory=list)
    segment: Optional[str] = None
    filters: dict = field(default_factory=dict)
    workflow_type: Optional[str] = None
    auto_approve: bool = False
    user_id: str = "system"
    metadata: dict = field(default_factory=dict)