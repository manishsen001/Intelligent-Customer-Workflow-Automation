"""Base AI Agent for task understanding and workflow selection."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from openai import OpenAI

from src.config.logging_config import logger
from src.config.settings import settings


class WorkflowType(Enum):
    """Available workflow types."""

    TASK_AUTOMATION = "task_automation"
    EMAIL_AUTOMATION = "email_automation"
    REMINDER = "reminder"
    CUSTOMER_FOLLOWUP = "customer_followup"
    INACTIVE_REENGAGEMENT = "inactive_reengagement"
    HIGH_VALUE_OUTREACH = "high_value_outreach"
    PAYMENT_COLLECTION = "payment_collection"
    SUPPORT_FOLLOWUP = "support_followup"
    NEW_LEAD_QUALIFICATION = "new_lead_qualification"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


@dataclass
class AgentResponse:
    """Response from the AI agent."""

    workflow_type: WorkflowType
    action: str
    parameters: dict[str, Any]
    confidence: float
    reasoning: str


class BaseAgent(ABC):
    """Base class for AI agents."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
    ):
        llm_config = settings.get_llm_config()
        self.client = OpenAI(
            api_key=api_key or llm_config["api_key"],
            base_url=base_url or llm_config["base_url"],
        )
        self.model = model or llm_config["model"]
        self.temperature = temperature if temperature is not None else llm_config["temperature"]
        self._provider = settings.LLM_PROVIDER

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""

    @abstractmethod
    def get_available_actions(self) -> list[dict[str, Any]]:
        """Get available actions for this agent."""

    def parse_response(self, response_text: str) -> AgentResponse:
        """Parse the AI response into structured format."""
        try:
            data = json.loads(response_text)
            return AgentResponse(
                workflow_type=WorkflowType(data.get("workflow_type", "unknown")),
                action=data.get("action", ""),
                parameters=data.get("parameters", {}),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse agent response: {e}")
            return AgentResponse(
                workflow_type=WorkflowType.UNKNOWN,
                action="",
                parameters={},
                confidence=0.0,
                reasoning=f"Parse error: {e!s}",
            )

    def _get_extra_body(self) -> dict | None:
        """Get provider-specific extra body parameters."""
        if self._provider == "nvidia":
            return {"chat_template_kwargs": {"enable_thinking": True}}
        return None

    def process(self, user_input: str) -> AgentResponse:
        """Process user input and return agent response."""
        try:
            from datetime import datetime
            system_prompt = self.get_system_prompt()
            actions = self.get_available_actions()
            
            # Get current date for relative date calculations
            current_date = datetime.now().strftime("%Y-%m-%d")
            current_day = datetime.now().strftime("%A")

            prompt = f"""
            Current Date: {current_date} ({current_day})
            User Request: {user_input}
            
            Available Actions:
            {json.dumps(actions, indent=2)}
            
            Respond with a JSON object containing:
            - workflow_type: one of {', '.join([w.value for w in WorkflowType])}
            - action: the specific action to take
            - parameters: dictionary of parameters for the action
            - confidence: float between 0 and 1
            - reasoning: explanation of why this action was chosen
            """

            extra_body = self._get_extra_body()
            create_kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": self.temperature,
                "response_format": {"type": "json_object"},
            }
            if extra_body:
                create_kwargs["extra_body"] = extra_body

            response = self.client.chat.completions.create(**create_kwargs)

            response_text = response.choices[0].message.content or ""
            logger.info(f"Agent response: {response_text}")

            return self.parse_response(response_text)

        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            return AgentResponse(
                workflow_type=WorkflowType.UNKNOWN,
                action="",
                parameters={},
                confidence=0.0,
                reasoning=f"Processing error: {e!s}",
            )


class WorkflowAgent(BaseAgent):
    """Main agent for understanding user tasks and selecting workflows."""

    def get_system_prompt(self) -> str:
        return """You are an AI Customer Workflow Automation Assistant. Your job is to understand user requests 
        and determine which customer workflow automation action to execute. You have access to customer-focused 
        workflow types:
        
        1. CUSTOMER_FOLLOWUP - For general customer follow-up based on various triggers (inactivity, support issues, etc.)
        
        2. INACTIVE_REENGAGEMENT - Re-engage inactive customers with personalized outreach
        
        3. HIGH_VALUE_OUTREACH - Proactive outreach to high-value customers
        
        4. PAYMENT_COLLECTION - Follow up on overdue payments
        
        5. SUPPORT_FOLLOWUP - Follow up on open support issues
        
        6. NEW_LEAD_QUALIFICATION - Qualify and nurture new leads
        
        7. TASK_AUTOMATION - For general task automation like file operations, data processing, 
           web scraping, API calls, scheduling tasks, etc.
        
        8. EMAIL_AUTOMATION - For sending emails, reading emails, managing email templates, 
           email scheduling, etc.
        
        9. REMINDER - For setting reminders, managing calendar events, notifications, etc.
        
        10. CUSTOM - For custom workflows combining multiple actions
        
        11. UNKNOWN - For informational requests, general questions, capability explanations, 
            or ambiguous requests that need clarification.
            - Use provide_information for explanations, capability overviews, and general questions.
            - Use ask_clarification when the user's intent is unclear and cannot be mapped to a specific automation.
        
        IMPORTANT DATETIME FORMATTING:
        - For reminder actions (set_reminder, set_calendar_event), the trigger_time/start_time/end_time 
          parameters MUST be in ISO 8601 format: YYYY-MM-DDTHH:MM:SS (e.g., "2025-01-15T14:30:00")
        - Do NOT use natural language like "tomorrow at 9 AM" - convert to ISO format
        - Use the user's local timezone
        - If the user says "tomorrow at 9 AM", calculate the actual date and use ISO format
        - If the user says "in 2 hours", add 2 hours to current time and use ISO format
        
        CUSTOMER-FOCUSED RULES:
        - Always use customer_search first to identify target customers
        - Use customer_analysis to score/segment customers before taking actions
        - Generate emails before sending (send_email requires approval)
        - Create reminders for follow-ups
        - Set approval_required to "required" for external actions (send_email)
        - Set approval_required to "optional" for internal actions (create_task, create_reminder)
        - Always include customer_id in parameters when targeting specific customers
        
        INFORMATONAL REQUEST HANDLING:
        - If the user is asking for information, explanations, or capabilities (not requesting an action),
          use workflow_type: "unknown" and action: "provide_information"
        - Provide the answer directly in the reasoning field
        - Do not include unnecessary parameters
        
        AMBIGUOUS REQUEST HANDLING:
        - If the user's request is unclear and could map to multiple workflows,
          use workflow_type: "unknown" and action: "ask_clarification"
        - Ask a specific clarifying question in the reasoning field
        
        EMAIL ADDRESS HANDLING:
        - If the user wants to send an email but does NOT provide an explicit recipient email address,
          use workflow_type: "unknown" and action: "ask_clarification"
        - NEVER invent, guess, or use placeholder email addresses (e.g., test@example.com, john@example.com, customer@example.com)
        - Only use an email address if the user explicitly provided it in their request
        - If the user says "my test email", "my email", "test address", etc. without the actual address, ask for clarification

        EMAIL WORKFLOW SELECTION:
        - For ANY direct email sending request (even mentioning a customer name, customer ID, or context like support tickets),
          use workflow_type: "email_automation" with action: "send_email"
        - The email_automation send_email action supports direct emails (to/recipients) AND registered customer lookup (customer_id, customer_name)
        - Customer-focused workflows (support_followup, customer_followup, etc.) are for MULTI-STEP automation sequences involving search, analysis, and multiple actions - NOT for simple direct email sending
        - Only use support_followup, customer_followup, etc. when the user explicitly requests a follow-up WORKFLOW (multiple automated steps)

        TASK CREATION FOR REGISTERED CUSTOMERS:
        - When the user says "create a task", "create a follow-up", "set a task", etc. AND mentions a person/customer name:
          * If the name could be a registered customer, use workflow_type: "support_followup" with action: "create_task"
          * Extract customer_name from the request
          * Convert natural language dates (tomorrow, next week, next Monday, etc.) to ISO 8601 format (YYYY-MM-DDTHH:MM:SS) using the Current Date provided above
          * Use default time of 09:00:00 if only date is given (e.g., if today is 2025-01-15, "tomorrow" -> "2025-01-16T09:00:00")
          * Set priority based on language: "high priority" -> "high", "urgent" -> "high", "low priority" -> "low", default -> "medium"
          * Use the request context for title and description
        - Only use ask_clarification if:
          * No customer name is mentioned AND no customer_id provided
          * The mentioned name cannot be resolved (but still route to support_followup with customer_name - let execution handle not-found)
          * The request is genuinely ambiguous between personal reminder and customer task

        Analyze the user's request carefully and choose the most appropriate workflow type and action.
        Always respond with valid JSON."""

    def get_available_actions(self) -> list[dict[str, Any]]:
        return [
            {
                "workflow_type": "customer_followup",
                "actions": [
                    {
                        "name": "customer_search",
                        "description": "Search and filter customers by segment, status, payment status, support status, and custom criteria.",
                    },
                    {
                        "name": "customer_analysis",
                        "description": "Analyze customers using AI to generate insights, segments, scores, and recommendations.",
                    },
                    {
                        "name": "create_customer_follow_up",
                        "description": "Create a follow-up task for one or more customers with title, reason, due date, and priority.",
                    },
                    {
                        "name": "update_customer_follow_up",
                        "description": "Update the status of a customer follow-up (pending, in_progress, waiting_approval, completed, cancelled, overdue).",
                    },
                    {
                        "name": "get_customer_follow_ups",
                        "description": "Get follow-ups for customers with optional filters (pending, upcoming, overdue, high priority).",
                    },
                    {
                        "name": "customer_segment",
                        "description": "Segment customers based on various criteria and get segment distribution.",
                    },
                    {
                        "name": "create_task",
                        "description": "Create a follow-up task for one or more customers with title, description, due date, and priority.",
                    },
                    {
                        "name": "generate_email",
                        "description": "Generate personalized email drafts for customers based on their profile, segment, and context.",
                    },
                    {
                        "name": "send_email",
                        "description": "Send emails to customers with approval workflow. Requires approval for external email sending.",
                    },
                    {
                        "name": "create_reminder",
                        "description": "Create reminders for customer follow-ups with trigger time and frequency.",
                    },
                    {
                        "name": "schedule_workflow",
                        "description": "Schedule a workflow to run periodically (daily, weekly, monthly) with specified parameters.",
                    },
                    {
                        "name": "customer_report",
                        "description": "Generate customer reports including segment distribution, engagement metrics, and follow-up summaries.",
                    },
                    {
                        "name": "request_approval",
                        "description": "Request human approval for sensitive actions like sending emails.",
                    },
                ],
            },
            {
                "workflow_type": "inactive_reengagement",
                "actions": [
                    {
                        "name": "customer_search",
                        "description": "Search and filter customers by segment, status, payment status, support status, and custom criteria.",
                    },
                    {
                        "name": "customer_analysis",
                        "description": "Analyze customers using AI to generate insights, segments, scores, and recommendations.",
                    },
                    {
                        "name": "generate_email",
                        "description": "Generate personalized email drafts for customers based on their profile, segment, and context.",
                    },
                    {
                        "name": "send_email",
                        "description": "Send emails to customers with approval workflow. Requires approval for external email sending.",
                    },
                    {
                        "name": "create_task",
                        "description": "Create a follow-up task for one or more customers with title, description, due date, and priority.",
                    },
                    {
                        "name": "create_reminder",
                        "description": "Create reminders for customer follow-ups with trigger time and frequency.",
                    },
                ],
            },
            {
                "workflow_type": "high_value_outreach",
                "actions": [
                    {
                        "name": "customer_search",
                        "description": "Search and filter customers by segment, status, payment status, support status, and custom criteria.",
                    },
                    {
                        "name": "customer_analysis",
                        "description": "Analyze customers using AI to generate insights, segments, scores, and recommendations.",
                    },
                    {
                        "name": "generate_email",
                        "description": "Generate personalized email drafts for customers based on their profile, segment, and context.",
                    },
                    {
                        "name": "send_email",
                        "description": "Send emails to customers with approval workflow. Requires approval for external email sending.",
                    },
                    {
                        "name": "create_task",
                        "description": "Create a follow-up task for one or more customers with title, description, due date, and priority.",
                    },
                    {
                        "name": "create_reminder",
                        "description": "Create reminders for customer follow-ups with trigger time and frequency.",
                    },
                ],
            },
            {
                "workflow_type": "payment_collection",
                "actions": [
                    {
                        "name": "customer_search",
                        "description": "Search and filter customers by segment, status, payment status, support status, and custom criteria.",
                    },
                    {
                        "name": "customer_analysis",
                        "description": "Analyze customers using AI to generate insights, segments, scores, and recommendations.",
                    },
                    {
                        "name": "generate_email",
                        "description": "Generate personalized email drafts for customers based on their profile, segment, and context.",
                    },
                    {
                        "name": "send_email",
                        "description": "Send emails to customers with approval workflow. Requires approval for external email sending.",
                    },
                    {
                        "name": "create_task",
                        "description": "Create a follow-up task for one or more customers with title, description, due date, and priority.",
                    },
                    {
                        "name": "create_reminder",
                        "description": "Create reminders for customer follow-ups with trigger time and frequency.",
                    },
                ],
            },
            {
                "workflow_type": "support_followup",
                "actions": [
                    {
                        "name": "customer_search",
                        "description": "Search and filter customers by segment, status, payment status, support status, and custom criteria.",
                    },
                    {
                        "name": "customer_analysis",
                        "description": "Analyze customers using AI to generate insights, segments, scores, and recommendations.",
                    },
                    {
                        "name": "generate_email",
                        "description": "Generate personalized email drafts for customers based on their profile, segment, and context.",
                    },
                    {
                        "name": "send_email",
                        "description": "Send emails to customers with approval workflow. Requires approval for external email sending.",
                    },
                    {
                        "name": "create_task",
                        "description": "Create a follow-up task for one or more customers with title, description, due date, and priority.",
                    },
                    {
                        "name": "create_reminder",
                        "description": "Create reminders for customer follow-ups with trigger time and frequency.",
                    },
                ],
            },
            {
                "workflow_type": "new_lead_qualification",
                "actions": [
                    {
                        "name": "customer_search",
                        "description": "Search and filter customers by segment, status, payment status, support status, and custom criteria.",
                    },
                    {
                        "name": "customer_analysis",
                        "description": "Analyze customers using AI to generate insights, segments, scores, and recommendations.",
                    },
                    {
                        "name": "generate_email",
                        "description": "Generate personalized email drafts for customers based on their profile, segment, and context.",
                    },
                    {
                        "name": "send_email",
                        "description": "Send emails to customers with approval workflow. Requires approval for external email sending.",
                    },
                    {
                        "name": "create_task",
                        "description": "Create a follow-up task for one or more customers with title, description, due date, and priority.",
                    },
                    {
                        "name": "create_reminder",
                        "description": "Create reminders for customer follow-ups with trigger time and frequency.",
                    },
                ],
            },
            {
                "workflow_type": "task_automation",
                "actions": [
                    {
                        "name": "run_script",
                        "description": "Execute a Python script or shell command",
                    },
                    {
                        "name": "file_operation",
                        "description": "Read, write, copy, move, or delete files",
                    },
                    {
                        "name": "data_processing",
                        "description": "Process CSV, JSON, Excel data",
                    },
                    {
                        "name": "web_scraping",
                        "description": "Scrape data from websites",
                    },
                    {"name": "api_call", "description": "Make HTTP API requests"},
                    {
                        "name": "schedule_task",
                        "description": "Schedule a recurring task",
                    },
                ],
            },
            {
                "workflow_type": "email_automation",
                "actions": [
                    {
                        "name": "send_email",
                        "description": "Send an email to one or more recipients. Supports direct email addresses (to/recipients) OR registered customer lookup via customer_id (e.g., 'CUST001') or customer_name (e.g., 'John Doe'). When customer_id or customer_name is provided, the system resolves the registered customer's email from the database. Does not require an explicit email address if customer_id or customer_name is provided. Use this for ANY direct email sending request, even when mentioning a customer by name.",
                    },
                    {
                        "name": "send_bulk_email",
                        "description": "Send emails to multiple recipients",
                    },
                    {
                        "name": "read_emails",
                        "description": "Read and filter emails from inbox",
                    },
                    {
                        "name": "create_template",
                        "description": "Create an email template",
                    },
                    {
                        "name": "schedule_email",
                        "description": "Schedule an email to be sent later",
                    },
                ],
            },
            {
                "workflow_type": "reminder",
                "actions": [
                    {
                        "name": "set_reminder",
                        "description": "Set a one-time or recurring reminder",
                    },
                    {
                        "name": "list_reminders",
                        "description": "List all active reminders",
                    },
                    {
                        "name": "cancel_reminder",
                        "description": "Cancel a specific reminder",
                    },
                    {
                        "name": "set_calendar_event",
                        "description": "Create a calendar event",
                    },
                ],
            },
            {
                "workflow_type": "custom",
                "actions": [
                    {
                        "name": "customer_search",
                        "description": "Search and filter customers by segment, status, payment status, support status, and custom criteria.",
                    },
                    {
                        "name": "customer_analysis",
                        "description": "Analyze customers using AI to generate insights, segments, scores, and recommendations.",
                    },
                    {
                        "name": "create_task",
                        "description": "Create a follow-up task for one or more customers with title, description, due date, and priority.",
                    },
                    {
                        "name": "generate_email",
                        "description": "Generate personalized email drafts for customers based on their profile, segment, and context.",
                    },
                    {
                        "name": "send_email",
                        "description": "Send emails to customers with approval workflow. Requires approval for external email sending.",
                    },
                    {
                        "name": "create_reminder",
                        "description": "Create reminders for customer follow-ups with trigger time and frequency.",
                    },
                    {
                        "name": "create_customer_follow_up",
                        "description": "Create a follow-up task for one or more customers with title, reason, due date, and priority.",
                    },
                    {
                        "name": "customer_segment",
                        "description": "Segment customers based on various criteria and get segment distribution.",
                    },
                ],
            },
            {
                "workflow_type": "unknown",
                "actions": [
                    {
                        "name": "provide_information",
                        "description": "Provide informational response, explanations, or answer general questions without executing a workflow. Use for consultation, capability explanations, and informational queries.",
                    },
                    {
                        "name": "ask_clarification",
                        "description": "Ask user for clarification when the request is ambiguous and cannot be mapped to a specific workflow.",
                    },
                ],
            },
        ]


def create_agent() -> WorkflowAgent:
    """Factory function to create the workflow agent."""
    return WorkflowAgent()


def check_llm_connection() -> tuple[bool, str]:
    """
    Test the LLM connection without exposing credentials.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        llm_config = settings.get_llm_config()
        if not llm_config.get("api_key"):
            return False, f"Missing {settings.LLM_PROVIDER.upper()}_API_KEY"
        
        client = OpenAI(
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
        )
        
        # Use a minimal test request
        response = client.chat.completions.create(
            model=llm_config["model"],
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            temperature=0,
        )
        
        if response.choices and response.choices[0].message.content:
            provider = settings.LLM_PROVIDER.upper()
            model = llm_config["model"]
            return True, f"{provider} connection OK (model: {model})"
        
        return False, "Empty response from LLM"
    
    except Exception as e:
        logger.error(f"LLM connection check failed: {e}")
        return False, f"Connection failed: {type(e).__name__}"