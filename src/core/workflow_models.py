"""Workflow planning models for Customer Workflow Automation System."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class WorkflowType(Enum):
    """Types of customer workflows."""
    CUSTOMER_FOLLOWUP = "customer_followup"
    INACTIVE_REENGAGEMENT = "inactive_reengagement"
    HIGH_VALUE_OUTREACH = "high_value_outreach"
    PAYMENT_COLLECTION = "payment_collection"
    SUPPORT_FOLLOWUP = "support_followup"
    NEW_LEAD_QUALIFICATION = "new_lead_qualification"
    CUSTOM = "custom"


class ActionType(Enum):
    """Types of actions in a workflow."""
    CUSTOMER_SEARCH = "customer_search"
    CUSTOMER_ANALYSIS = "customer_analysis"
    CREATE_TASK = "create_task"
    GENERATE_EMAIL = "generate_email"
    SEND_EMAIL = "send_email"
    CREATE_REMINDER = "create_reminder"
    SCHEDULE_WORKFLOW = "schedule_workflow"
    CUSTOMER_REPORT = "customer_report"
    REQUEST_APPROVAL = "request_approval"
    UPDATE_CUSTOMER = "update_customer"


class ApprovalRequired(Enum):
    """Approval requirement levels."""
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""
    name: str
    type: str  # "string", "integer", "number", "boolean", "array", "object"
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[list[str]] = None


@dataclass
class ToolSchema:
    """Schema for tool input validation."""
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for AI function calling (OpenAI format)."""
        properties = {}
        required = []
        for param in self.parameters:
            prop = {"type": param.type, "description": param.description}
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            if param.required:
                required.append(param.name)
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


@dataclass
class WorkflowStep:
    """A single step in a workflow plan."""
    step_id: str
    action: ActionType
    description: str
    parameters: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    approval_required: ApprovalRequired = ApprovalRequired.NONE
    approval_description: str = ""


@dataclass
class WorkflowPlan:
    """Structured workflow plan generated from natural language."""
    plan_id: str
    workflow_type: WorkflowType
    name: str
    description: str
    target_customers: dict  # Search criteria for target customers
    steps: list[WorkflowStep]
    approval_required: ApprovalRequired = ApprovalRequired.NONE
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "user"
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "workflow_type": self.workflow_type.value,
            "name": self.name,
            "description": self.description,
            "target_customers": self.target_customers,
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action.value,
                    "description": s.description,
                    "parameters": s.parameters,
                    "depends_on": s.depends_on,
                    "approval_required": s.approval_required.value,
                    "approval_description": s.approval_description,
                }
                for s in self.steps
            ],
            "approval_required": self.approval_required.value,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowPlan":
        """Create from dictionary."""
        steps = [
            WorkflowStep(
                step_id=s["step_id"],
                action=ActionType(s["action"]),
                description=s["description"],
                parameters=s["parameters"],
                depends_on=s.get("depends_on", []),
                approval_required=ApprovalRequired(s.get("approval_required", "none")),
                approval_description=s.get("approval_description", ""),
            )
            for s in data.get("steps", [])
        ]
        return cls(
            plan_id=data["plan_id"],
            workflow_type=WorkflowType(data["workflow_type"]),
            name=data["name"],
            description=data["description"],
            target_customers=data["target_customers"],
            steps=steps,
            approval_required=ApprovalRequired(data.get("approval_required", "none")),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
            created_by=data.get("created_by", "user"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class WorkflowExecutionContext:
    """Context passed between workflow steps."""
    plan: WorkflowPlan
    step_results: dict[str, ToolResult] = field(default_factory=dict)
    selected_customers: list[dict] = field(default_factory=list)
    current_step: Optional[str] = None
    variables: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)