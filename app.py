"""Main Streamlit Application for Intelligent Customer Workflow Automation System."""

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
IST = ZoneInfo("Asia/Kolkata")

import pandas as pd
import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.agents.base_agent import WorkflowType, create_agent
from src.config.logging_config import logger
from src.config.settings import settings
from src.utils.datetime_parser import parse_relative_datetime
from src.workflows.email_automation import (
    EmailMessage,
    EmailResult,
    create_email_automation,
)
from src.workflows.reminder import (
    ReminderFrequency,
    ReminderResult,
    create_reminder_manager,
)
from src.workflows.task_automation import TaskResult, create_task_automation
from src.db.models import WorkflowStatus
from src.services.follow_up import create_follow_up_service
from src.services.scheduled_workflow import create_scheduled_workflow_engine
from src.services.customer_email import create_customer_email_service
from src.services.customer_intelligence import create_customer_intelligence
from src.services.customer_data import create_customer_data_service
from src.services.workflow_execution import create_workflow_execution_service
from src.db import init_database
from src.db.models import Customer, CustomerSegment, CustomerStatus
from src.db.repositories import CustomerRepository
from src.db import get_db
from src.customer import create_customer_analyzer
from src.customer.models import CUSTOMER_SEGMENTS

# Page config
st.set_page_config(
    page_title="Intelligent Customer Workflow Automation",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton > button {
        width: 100%;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        color: #155724;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.5rem;
        color: #721c24;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.5rem;
        color: #0c5460;
    }
</style>
""",
    unsafe_allow_html=True,
)


# Initialize session state
if "agent" not in st.session_state:
    st.session_state.agent = create_agent()
if "task_automation" not in st.session_state:
    st.session_state.task_automation = create_task_automation()
if "email_automation" not in st.session_state:
    st.session_state.email_automation = create_email_automation()
if "reminder_manager" not in st.session_state:
    st.session_state.reminder_manager = create_reminder_manager()
if "follow_up_service" not in st.session_state:
    st.session_state.follow_up_service = create_follow_up_service()
if "workflow_execution" not in st.session_state:
    st.session_state.workflow_execution = create_workflow_execution_service()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None


def display_result(result: any, title: str = "Result"):
    """Display a result object in a nice format."""
    if hasattr(result, "success"):
        if result.success:
            # Different result types have different success message fields
            if hasattr(result, "message") and result.message:
                # EmailResult, ReminderResult
                st.success(f"**{title}**: {result.message}")
            elif hasattr(result, "output") and result.output is not None:
                # TaskResult
                st.success(f"**{title}**: Completed successfully")
            else:
                st.success(f"**{title}**: Success")

            # Show details if available (EmailResult)
            if hasattr(result, "details") and result.details:
                with st.expander("Details"):
                    st.json(result.details)

            # Show output if available (TaskResult)
            if hasattr(result, "output") and result.output is not None:
                with st.expander("Output"):
                    if isinstance(result.output, (dict, list)):
                        st.json(result.output)
                    else:
                        st.text(str(result.output))

            # Show reminder info if available (ReminderResult)
            if hasattr(result, "reminder") and result.reminder:
                with st.expander("Reminder"):
                    st.json({
                        "id": result.reminder.id,
                        "title": result.reminder.title,
                        "description": result.reminder.description,
                        "trigger_time": result.reminder.trigger_time,
                        "frequency": result.reminder.frequency.value,
                        "enabled": result.reminder.enabled,
                    })
            if hasattr(result, "reminders") and result.reminders:
                with st.expander("Reminders"):
                    st.json([{
                        "id": r.id,
                        "title": r.title,
                        "description": r.description,
                        "trigger_time": r.trigger_time,
                        "frequency": r.frequency.value,
                        "enabled": r.enabled,
                    } for r in result.reminders])

            # Show execution time if available (TaskResult)
            if hasattr(result, "execution_time") and result.execution_time:
                st.caption(f"Execution time: {result.execution_time:.2f}s")
        else:
            # Error case - all types have error field
            st.error(f"**{title}**: {result.error or 'Unknown error'}")
    else:
        st.json(result)


def main():
    # Check for valid LLM API key
    llm_config = settings.get_llm_config()
    if not llm_config.get("api_key"):
        st.error(
            f"❌ **Missing API Key**\n\n"
            f"Please set `{settings.LLM_PROVIDER.upper()}_API_KEY` in your `.env` file.\n\n"
            f"Current provider: **{settings.LLM_PROVIDER.upper()}**\n"
            f"Expected variable: **{settings.LLM_PROVIDER.upper()}_API_KEY**\n\n"
            f"Copy `.env.example` to `.env` and add your API key."
        )
        st.stop()

    # Header
    st.markdown(
        '<div class="main-header">🤖 Intelligent Customer Workflow Automation System</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-header">Automate customer follow-ups, engagement, and communications with AI</div>',
        unsafe_allow_html=True,
    )

    # Sidebar
    with st.sidebar:
        st.header("🎛️ Control Panel")

        # Mode selection
        mode = st.radio(
            "Select Mode",
            ["💬 AI Chat", "⚙️ Task Automation", "📧 Email Automation", "⏰ Reminders", "🔄 Follow-ups", "⏰ Scheduled Workflows", "👥 Customer Dashboard", "🔍 Customer Analysis", "📊 Customer Segmentation"],
            index=0,
        )

        st.divider()

        # Settings
        with st.expander("⚙️ Settings"):
            llm_config = settings.get_llm_config()
            st.text_input("LLM Provider", value=settings.LLM_PROVIDER.upper(), disabled=True)
            st.text_input("Model", value=llm_config["model"], disabled=True)
            st.text_input("Base URL", value=llm_config["base_url"] or "Default (OpenAI)", disabled=True)
            st.text_input("SMTP Server", value=settings.SMTP_SERVER, disabled=True)
            st.text_input("Email", value=settings.EMAIL_ADDRESS, disabled=True)

            if st.button("🔄 Reload Config"):
                st.rerun()

        st.divider()

        # Quick stats
        st.subheader("📊 Customer Dashboard")
        
        # Initialize customer intelligence service
        if "customer_intelligence" not in st.session_state:
            st.session_state.customer_intelligence = create_customer_intelligence()
        
        # Get quick stats from database
        db = next(get_db())
        repo = CustomerRepository(db)
        stats = repo.get_dashboard_stats()
        db.close()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Customers", stats.get("total_customers", 0))
            st.metric("Active Customers", stats.get("active_customers", 0))
        with col2:
            st.metric("High-Value Customers", stats.get("high_value_customers", 0))
            st.metric("At-Risk Customers", stats.get("at_risk_customers", 0))
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Payment Risk", stats.get("payment_risk_customers", 0))
            st.metric("Overdue Payments", stats.get("overdue_payments", 0))
        with col2:
            st.metric("Customers Needing Follow-up", stats.get("customers_needing_followup", 0))
            st.metric("Pending Approvals", stats.get("pending_approvals", 0))

        st.divider()

        # Follow-up stats
        reminders = st.session_state.reminder_manager.list_reminders(
            include_disabled=True
        )
        if reminders.success and reminders.reminders:
            active = sum(1 for r in reminders.reminders if r.enabled)
            st.metric("Active Reminders", active)
            st.metric("Total Reminders", len(reminders.reminders))

        st.divider()

        # Health check
        if st.button("🔍 Test LLM Connection"):
            with st.spinner("Testing connection..."):
                from src.agents import check_llm_connection
                success, message = check_llm_connection()
                if success:
                    st.success(message)
                else:
                    st.error(message)

        st.divider()
        st.caption(f"v{__import__('src').__version__}")

    # Main content based on mode
    if mode == "💬 AI Chat":
        render_chat_mode()
    elif mode == "⚙️ Task Automation":
        render_task_automation()
    elif mode == "📧 Email Automation":
        render_email_automation()
    elif mode == "⏰ Reminders":
        render_reminders()
    elif mode == "🔄 Follow-ups":
        render_followups()
    elif mode == "⏰ Scheduled Workflows":
        render_scheduled_workflows()
    elif mode == "👥 Customer Dashboard":
        render_customer_dashboard()
    elif mode == "🔍 Customer Analysis":
        render_customer_analysis()
    elif mode == "📊 Customer Segmentation":
        render_customer_segmentation()


def render_chat_mode():
    """Render the AI chat interface."""
    st.header("💬 AI Assistant")
    st.caption("Describe what you want to automate in natural language")

    # Chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("result"):
                display_result(msg["result"], "Result")

    # Chat input
    if prompt := st.chat_input(
        "What would you like to automate? (e.g., 'Send an email to john@example.com about meeting tomorrow', 'Set a reminder for 3pm', 'Run a script to process data.csv')"
    ):
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # Process with AI agent
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.agent.process(prompt)

                # Display reasoning
                st.markdown(f"**Reasoning**: {response.reasoning}")
                st.markdown(f"**Workflow**: {response.workflow_type.value}")
                st.markdown(f"**Action**: {response.action}")
                st.markdown(f"**Confidence**: {response.confidence:.0%}")

                # Check if this is an informational request or clarification request
                # These should NOT execute a workflow
                is_informational = (
                    response.workflow_type == WorkflowType.UNKNOWN
                    and response.action in ["provide_information", "ask_clarification", "none", ""]
                )

                if is_informational:
                    # For informational/clarification requests, show the AI response directly
                    # without executing a workflow
                    result = None
                    if response.action == "ask_clarification":
                        st.warning("❓ **Clarification needed**: " + response.reasoning)
                    # For provide_information, the reasoning already contains the answer
                else:
                    # Execute the action for automation workflows
                    result = execute_workflow(response)
                    display_result(result, "Execution Result")

                # Add to history
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": f"**Reasoning**: {response.reasoning}\n\n**Workflow**: {response.workflow_type.value}\n**Action**: {response.action}\n**Confidence**: {response.confidence:.0%}",
                        "result": result,
                    }
                )


def execute_workflow(response) -> any:
    """Execute the workflow based on agent response."""
    try:
        # Create workflow execution record
        wf_service = st.session_state.workflow_execution
        execution = wf_service.create_execution(
            workflow_id=response.workflow_type.value,
            workflow_name=response.workflow_type.value.replace("_", " ").title(),
            trigger_type="user_chat",
            trigger_data={"action": response.action, "confidence": response.confidence},
            input_data=response.parameters,
        )
        
        try:
            if response.workflow_type == WorkflowType.TASK_AUTOMATION:
                result = execute_task_automation(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.EMAIL_AUTOMATION:
                result = execute_email_automation(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.REMINDER:
                result = execute_reminder(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.CUSTOMER_FOLLOWUP:
                result = execute_customer_followup(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.INACTIVE_REENGAGEMENT:
                result = execute_inactive_reengagement(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.HIGH_VALUE_OUTREACH:
                result = execute_high_value_outreach(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.PAYMENT_COLLECTION:
                result = execute_payment_collection(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.SUPPORT_FOLLOWUP:
                result = execute_support_followup(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.NEW_LEAD_QUALIFICATION:
                result = execute_new_lead_qualification(response.action, response.parameters)
            elif response.workflow_type == WorkflowType.CUSTOM:
                result = execute_custom_workflow(response.action, response.parameters)
            else:
                class ErrorResult:
                    success = False
                    error = f"Unknown workflow type: {response.workflow_type}"
                return ErrorResult()
            
            # Store successful result
            wf_service.update_execution_output(
                execution_id=execution.id,
                output_data={"success": getattr(result, 'success', True), "result": str(result)},
                result_summary=str(result),
                status=WorkflowStatus.COMPLETED,
                execution_log=[{"action": response.action, "result": str(result)}],
            )
            return result
            
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            wf_service.update_execution_output(
                execution_id=execution.id,
                error_message=str(e),
                execution_log=[{"action": response.action, "error": str(e)}],
                status=WorkflowStatus.FAILED,
            )
            
            class ErrorResult:
                success = False
                error = str(e)
            return ErrorResult()
    except Exception as e:
        logger.error(f"Workflow execution record creation error: {e}")
        class ErrorResult:
            success = False
            error = str(e)
        return ErrorResult()


def execute_task_automation(action: str, params: dict) -> TaskResult:
    """Execute task automation action."""
    ta = st.session_state.task_automation

    if action == "run_script":
        return ta.run_script(params.get("script_path", ""), params.get("args"))
    elif action == "file_operation":
        return ta.file_operation(
            params.get("operation", ""), **params.get("kwargs", {})
        )
    elif action == "data_processing":
        return ta.data_processing(
            params.get("operation", ""), **params.get("kwargs", {})
        )
    elif action == "web_scraping":
        return ta.web_scraping(params.get("url", ""), params.get("selector"))
    elif action == "api_call":
        return ta.api_call(
            params.get("method", "GET"),
            params.get("url", ""),
            **params.get("kwargs", {}),
        )
    elif action == "schedule_task":
        return ta.schedule_task(
            params.get("task_name", ""),
            params.get("schedule", ""),
            params.get("action", ""),
            **params.get("kwargs", {}),
        )
    else:

        class ErrorResult:
            success = False
            error = f"Unknown task action: {action}"

        return ErrorResult()


def execute_email_automation(action: str, params: dict) -> EmailResult:
    """Execute email automation action."""
    ea = st.session_state.email_automation

    if action == "send_email":
        # Support customer_id or customer_name lookup for registered customers
        recipients = params.get("recipients", [])
        if not recipients and params.get("to"):
            to = params.get("to")
            recipients = [to] if isinstance(to, str) else to

        # If no direct recipients, try to resolve via customer_id or customer_name
        if not recipients:
            customer_id = params.get("customer_id")
            customer_name = params.get("customer_name")

            if customer_id or customer_name:
                db = next(get_db())
                repo = CustomerRepository(db)
                customer = None

                if customer_id:
                    customer = repo.get_by_customer_id(customer_id)
                elif customer_name:
                    # Search by name
                    customers = repo.list_customers(filters={"search": customer_name}, limit=1)
                    customer = customers[0] if customers else None

                if not customer:
                    class ErrorResult:
                        success = False
                        error = f"Customer not found: {customer_id or customer_name}"
                    return ErrorResult()

                if not customer.email:
                    class ErrorResult:
                        success = False
                        error = f"Customer '{customer.name}' (ID: {customer.customer_id}) has no email address"
                    return ErrorResult()

                recipients = [customer.email]

        if not recipients:
            class ErrorResult:
                success = False
                error = "No recipient email address provided. Use 'to', 'recipients', 'customer_id', or 'customer_name'."
            return ErrorResult()

        msg = EmailMessage(
            subject=params.get("subject", ""),
            sender=params.get("sender", ""),
            recipients=recipients,
            body=params.get("body", ""),
            html_body=params.get("html_body"),
            attachments=params.get("attachments", []),
            cc=params.get("cc", []),
            bcc=params.get("bcc", []),
        )
        return ea.send_email(msg)
    elif action == "send_bulk_email":
        emails = []
        for e in params.get("emails", []):
            emails.append(EmailMessage(**e))
        return ea.send_bulk_email(emails, params.get("delay", 1.0))
    elif action == "read_emails":
        return ea.read_emails(
            params.get("folder", "INBOX"),
            params.get("criteria", "ALL"),
            params.get("limit", 10),
        )
    elif action == "create_template":
        return ea.create_template(
            params.get("name", ""),
            params.get("subject", ""),
            params.get("body", ""),
            params.get("html_body"),
        )
    elif action == "list_templates":
        return ea.list_templates()
    else:

        class ErrorResult:
            success = False
            error = f"Unknown email action: {action}"

        return ErrorResult()


def execute_reminder(action: str, params: dict) -> ReminderResult:
    """Execute reminder action."""
    rm = st.session_state.reminder_manager

    def _parse_time(time_str: str) -> str:
        """Parse time string to ISO format, handling natural language."""
        if not time_str:
            return ""
        # Try ISO format first
        try:
            datetime.fromisoformat(time_str)
            return time_str
        except ValueError:
            pass
        # Try natural language parsing
        parsed = parse_relative_datetime(time_str)
        if parsed:
            return parsed.isoformat()
        # Return original if unable to parse (will be handled by set_reminder)
        return time_str

    if action == "set_reminder":
        trigger_time = _parse_time(params.get("trigger_time", ""))
        return rm.set_reminder(
            params.get("title", ""),
            params.get("description", ""),
            trigger_time,
            params.get("frequency", "once"),
        )
    elif action == "list_reminders":
        return rm.list_reminders(params.get("include_disabled", False))
    elif action == "cancel_reminder":
        return rm.cancel_reminder(params.get("reminder_id", ""))
    elif action == "set_calendar_event":
        start_time = _parse_time(params.get("start_time", ""))
        end_time = params.get("end_time")
        if end_time:
            end_time = _parse_time(end_time)
        return rm.set_calendar_event(
            params.get("title", ""),
            params.get("description", ""),
            start_time,
            end_time,
            params.get("location"),
        )
    else:

        class ErrorResult:
            success = False
            error = f"Unknown reminder action: {action}"

        return ErrorResult()


# ============================================================
# Customer-Focused Workflow Execution Functions
# ============================================================

def execute_customer_followup(action: str, params: dict) -> any:
    """Execute customer follow-up workflow actions."""
    from src.services.follow_up import create_follow_up_service
    
    follow_up_service = create_follow_up_service()
    
    if action == "create_customer_follow_up":
        follow_up = follow_up_service.create_follow_up(
            customer_id=params.get("customer_id", ""),
            reason=params.get("reason", ""),
            due_date=params.get("due_date", ""),
            priority=params.get("priority", 50),
            next_action=params.get("next_action", ""),
        )
        # Wrap in result object for display_result compatibility
        class FollowUpResult:
            success = True
            follow_up = None
            def __init__(self, fu):
                self.success = True
                self.message = f"Follow-up created for customer {fu.customer_id}"
                self.follow_up = fu
        return FollowUpResult(follow_up)
    elif action == "update_customer_follow_up":
        return follow_up_service.update_status(
            follow_up_id=params.get("follow_up_id", 0),
            status=params.get("status", "pending"),
        )
    elif action == "list_follow_ups":
        return follow_up_service.list_follow_ups(
            customer_id=params.get("customer_id"),
            status=params.get("status"),
        )
    elif action == "get_overdue_follow_ups":
        return follow_up_service.get_overdue_follow_ups()
    elif action == "get_upcoming_follow_ups":
        return follow_up_service.get_upcoming_follow_ups(
            days=params.get("days", 7)
        )
    elif action == "customer_analysis":
        # Handle customer analysis action
        from src.services.customer_intelligence import create_customer_intelligence
        from src.db import get_db
        from src.db.repositories import CustomerRepository
        
        db = next(get_db())
        try:
            repo = CustomerRepository(db)
            intelligence = create_customer_intelligence()
            
            customer_ids = params.get("customer_ids", [])
            use_ai = params.get("use_ai", True)
            
            # If no customer_ids provided, check if we have selected customers in context
            # (this would be set by a previous customer_search step)
            if not customer_ids:
                # In a workflow context, this would be populated from previous step
                # For now, we'll return an error if no customer_ids provided
                return {
                    "success": False,
                    "error": "customer_ids parameter is required for customer_analysis"
                }
            
            customers = []
            for cid in customer_ids:
                customer = repo.get_by_customer_id(cid)
                if customer:
                    customers.append(customer)
            
            if not customers:
                return {
                    "success": False,
                    "error": f"No valid customers found for IDs: {customer_ids}"
                }
            
            intelligence = create_customer_intelligence()
            analyses = intelligence.batch_analyze(customers, use_ai=params.get("use_ai", True))
            
            # Update customer records with analysis
            for customer, analysis in zip(customers, analyses):
                intelligence.update_customer_scores(customer, analysis)
            
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
            
            return {
                "success": True,
                "data": {
                    "analyses": analysis_data,
                    "count": len(analysis_data),
                }
            }
        
        except Exception as e:
            logger.error(f"Customer analysis failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    else:
        class ErrorResult:
            success = False
            error = f"Unknown customer followup action: {action}"
        return ErrorResult()


def execute_inactive_reengagement(action: str, params: dict) -> any:
    """Execute inactive customer re-engagement workflow actions."""
    from src.services.customer_intelligence import create_customer_intelligence
    from src.services.follow_up import create_follow_up_service
    from src.services.customer_email import create_customer_email_service
    from src.db import get_db
    from src.db.repositories import CustomerRepository
    from src.services.customer_email import EmailTemplateType
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    intelligence = create_customer_intelligence()
    follow_up_service = create_follow_up_service()
    email_service = create_customer_email_service()
    
    if action == "find_inactive_customers":
        # Find inactive customers
        from src.services.customer_intelligence import create_customer_intelligence
        intelligence = create_customer_intelligence()
        # This would need a specific method - for now use customer_search
        pass
    
    if action == "create_reengagement_tasks":
        # This would create follow-up tasks for inactive customers
        pass
    
    if action == "send_reengagement_emails":
        # This would send re-engagement emails
        pass
    
    class ErrorResult:
        success = False
        error = f"Inactive reengagement action '{action}' not fully implemented yet"
    
    return ErrorResult()


def execute_high_value_outreach(action: str, params: dict) -> any:
    """Execute high-value customer outreach workflow actions."""
    class ErrorResult:
        success = False
        error = f"High value outreach action '{action}' not fully implemented yet"
    return ErrorResult()


def execute_payment_collection(action: str, params: dict) -> any:
    """Execute payment collection workflow actions."""
    from src.services.customer_intelligence import create_customer_intelligence
    from src.services.customer_email import create_customer_email_service
    from src.db import get_db
    from src.db.repositories import CustomerRepository
    
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    intelligence = create_customer_intelligence()
    email_service = create_customer_email_service()
    
    if action == "find_overdue_customers":
        # Find customers with overdue payments
        customers = customer_repo.list_customers(filters={"payment_status": "overdue"})
        return {"customers": [{"customer_id": c.customer_id, "name": c.name, "email": c.email, "outstanding": c.outstanding_amount} for c in customers]}
    
    if action == "send_payment_reminders":
        # Send payment reminder emails
        pass
    
    if action == "create_collection_tasks":
        # Create follow-up tasks for payment collection
        pass
    
    class ErrorResult:
        success = False
        error = f"Payment collection action '{action}' not fully implemented yet"
    return ErrorResult()


def execute_support_followup(action: str, params: dict) -> any:
    """Execute support follow-up workflow actions."""
    if action == "create_task":
        from src.db import get_db
        from src.db.repositories import CustomerRepository, TaskRepository
        from src.db.models import Task, TaskStatus
        from datetime import datetime
        
        db = next(get_db())
        customer_repo = CustomerRepository(db)
        task_repo = TaskRepository(db)
        
        # Resolve customer by customer_id or customer_name
        customer_id = params.get("customer_id")
        customer_name = params.get("customer_name")
        customer = None
        
        if customer_id:
            customer = customer_repo.get_by_customer_id(customer_id)
        elif customer_name:
            customers = customer_repo.list_customers(filters={"search": customer_name}, limit=1)
            customer = customers[0] if customers else None
        
        if not customer:
            class ErrorResult:
                success = False
                error = f"Customer not found: {customer_id or customer_name}"
            return ErrorResult()
        
        # Parse priority (high=80, medium=50, low=20)
        priority_map = {"high": 80, "medium": 50, "low": 20}
        priority_str = str(params.get("priority", "medium")).lower()
        priority = priority_map.get(priority_str, 50)
        
        # Parse due_date if provided
        due_date = None
        if params.get("due_date"):
            try:
                due_date = datetime.fromisoformat(params["due_date"])
            except ValueError:
                pass  # Ignore invalid date
        
        # Create the task
        task = Task(
            customer_id=customer.id,
            title=params.get("title", "Support follow-up task"),
            description=params.get("description", ""),
            task_type="support_followup",
            status=TaskStatus.PENDING,
            priority=priority,
            due_date=due_date,
            assigned_to=params.get("assigned_to"),
            task_metadata={"workflow": "support_followup", "action": "create_task"},
        )
        created_task = task_repo.create(task)
        db.commit()
        
        class SuccessResult:
            success = True
            data = {
                "task_id": created_task.id,
                "customer_id": customer.customer_id,
                "customer_name": customer.name,
                "title": created_task.title,
                "description": created_task.description,
                "priority": created_task.priority,
                "status": created_task.status.value,
                "due_date": created_task.due_date.isoformat() if created_task.due_date else None,
                "created_at": created_task.created_at.isoformat(),
            }
            message = f"Task created for customer {customer.name} (ID: {customer.customer_id})"
        
        return SuccessResult()
    
    class ErrorResult:
        success = False
        error = f"Support followup action '{action}' not implemented"
    return ErrorResult()


def execute_new_lead_qualification(action: str, params: dict) -> any:
    """Execute new lead qualification workflow actions."""
    class ErrorResult:
        success = False
        error = f"New lead qualification action '{action}' not fully implemented yet"
    return ErrorResult()


def execute_custom_workflow(action: str, params: dict) -> any:
    """Execute custom workflow actions."""
    class ErrorResult:
        success = False
        error = f"Custom workflow action '{action}' not fully implemented yet"
    return ErrorResult()


def render_task_automation():
    """Render task automation interface."""
    st.header("⚙️ Task Automation")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📁 File Operations",
            "📊 Data Processing",
            "🌐 Web/API",
            "📜 Scripts",
            "📅 Scheduler",
        ]
    )

    ta = st.session_state.task_automation

    with tab1:
        st.subheader("File Operations")
        op = st.selectbox(
            "Operation", ["read", "write", "copy", "move", "delete", "list"]
        )

        if op == "read":
            path = st.text_input("File Path", placeholder="data/file.txt")
            if st.button("Read File"):
                result = ta.file_operation("read", path=path)
                display_result(result)

        elif op == "write":
            path = st.text_input("File Path", placeholder="output/result.txt")
            content = st.text_area("Content")
            if st.button("Write File"):
                result = ta.file_operation("write", path=path, content=content)
                display_result(result)

        elif op == "list":
            path = st.text_input("Directory Path", placeholder=".")
            pattern = st.text_input("Pattern", value="*")
            if st.button("List Files"):
                result = ta.file_operation("list", path=path, pattern=pattern)
                display_result(result)

    with tab2:
        st.subheader("Data Processing")
        op = st.selectbox(
            "Operation",
            [
                "read_csv",
                "write_csv",
                "read_json",
                "write_json",
                "read_excel",
                "write_excel",
                "transform",
            ],
        )

        if op in ["read_csv", "read_json", "read_excel"]:
            path = st.text_input("File Path")
            if st.button(f"Read {op.split('_')[1].upper()}"):
                result = ta.data_processing(op, path=path)
                display_result(result)

        elif op in ["write_csv", "write_json", "write_excel"]:
            path = st.text_input("Output Path")
            data_text = st.text_area("Data (JSON array)", value="[]")
            if st.button(f"Write {op.split('_')[1].upper()}"):
                try:
                    data = json.loads(data_text)
                    result = ta.data_processing(op, path=path, data=data)
                    display_result(result)
                except json.JSONDecodeError:
                    st.error("Invalid JSON")

        elif op == "transform":
            data_text = st.text_area("Input Data (JSON array)", value="[]")
            col1, col2 = st.columns(2)
            with col1:
                filter_text = st.text_area("Filter (JSON)", value="{}")
            with col2:
                select_cols = st.text_input("Select Columns (comma-separated)")
            if st.button("Transform"):
                try:
                    data = json.loads(data_text)
                    filter_dict = json.loads(filter_text)
                    select_list = (
                        [c.strip() for c in select_cols.split(",")]
                        if select_cols
                        else None
                    )
                    kwargs = {"data": data}
                    if filter_dict:
                        kwargs["filter"] = filter_dict
                    if select_list:
                        kwargs["select"] = select_list
                    result = ta.data_processing("transform", **kwargs)
                    display_result(result)
                except json.JSONDecodeError:
                    st.error("Invalid JSON")

    with tab3:
        st.subheader("Web Scraping & API Calls")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Web Scraping**")
            url = st.text_input("URL", placeholder="https://example.com")
            selector = st.text_input("CSS Selector (optional)", placeholder=".title")
            if st.button("Scrape"):
                result = ta.web_scraping(url, selector)
                display_result(result)

        with col2:
            st.markdown("**API Call**")
            method = st.selectbox("Method", ["GET", "POST", "PUT", "DELETE"])
            api_url = st.text_input(
                "API URL", placeholder="https://api.example.com/data"
            )
            headers = st.text_area("Headers (JSON)", value="{}")
            body = st.text_area("Body (JSON)", value="{}")
            if st.button("Call API"):
                try:
                    result = ta.api_call(
                        method,
                        api_url,
                        headers=json.loads(headers),
                        json=json.loads(body) if body != "{}" else None,
                    )
                    display_result(result)
                except json.JSONDecodeError:
                    st.error("Invalid JSON in headers or body")

    with tab4:
        st.subheader("Run Scripts")
        script = st.text_input("Script Path", placeholder="scripts/process.py")
        args = st.text_input(
            "Arguments (space-separated)",
            placeholder="--input data.csv --output result.csv",
        )
        if st.button("Run Script"):
            arg_list = args.split() if args else None
            result = ta.run_script(script, arg_list)
            display_result(result)

    with tab5:
        st.subheader("Schedule Tasks")
        task_name = st.text_input("Task Name", placeholder="daily_report")
        schedule = st.text_input(
            "Cron Schedule", placeholder="0 9 * * * (daily at 9 AM)"
        )
        action = st.text_input("Action", placeholder="run_script")
        kwargs_text = st.text_area("Parameters (JSON)", value="{}")
        if st.button("Schedule Task"):
            try:
                result = ta.schedule_task(
                    task_name, schedule, action, **json.loads(kwargs_text)
                )
                display_result(result)
            except json.JSONDecodeError:
                st.error("Invalid JSON")


def render_email_automation():
    """Render email automation interface."""
    st.header("📧 Email Automation")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📨 Send Email", "📬 Read Emails", "📋 Templates", "📨 Bulk Send"]
    )

    ea = st.session_state.email_automation

    with tab1:
        st.subheader("Send Email")
        with st.form("send_email_form"):
            col1, col2 = st.columns(2)
            with col1:
                recipients = st.text_area(
                    "To (one per line)",
                    placeholder="recipient1@example.com\nrecipient2@example.com",
                )
                cc = st.text_area("CC (one per line)")
                bcc = st.text_area("BCC (one per line)")
            with col2:
                subject = st.text_input("Subject")
                attachments = st.text_area("Attachments (paths, one per line)")

            body = st.text_area("Body (Plain Text)", height=200)
            html_body = st.text_area("Body (HTML, optional)", height=150)

            if st.form_submit_button("📤 Send Email"):
                msg = EmailMessage(
                    subject=subject,
                    sender="",
                    recipients=[r.strip() for r in recipients.split("\n") if r.strip()],
                    body=body,
                    html_body=html_body if html_body else None,
                    attachments=[
                        a.strip() for a in attachments.split("\n") if a.strip()
                    ],
                    cc=[c.strip() for c in cc.split("\n") if c.strip()],
                    bcc=[b.strip() for b in bcc.split("\n") if b.strip()],
                )
                result = ea.send_email(msg)
                display_result(result)

    with tab2:
        st.subheader("Read Emails")
        col1, col2, col3 = st.columns(3)
        with col1:
            folder = st.text_input("Folder", value="INBOX")
        with col2:
            criteria = st.text_input("Criteria", value="UNSEEN")
        with col3:
            limit = st.number_input("Limit", min_value=1, max_value=100, value=10)

        if st.button("📥 Fetch Emails"):
            result = ea.read_emails(folder, criteria, limit)
            display_result(result)

            if result.success and result.details and result.details.get("emails"):
                for email_data in result.details["emails"]:
                    with st.expander(
                        f"{email_data['subject']} - {email_data['sender']}"
                    ):
                        st.text(f"Date: {email_data['date']}")
                        st.text(email_data["body"])

    with tab3:
        st.subheader("Email Templates")

        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("📋 List Templates"):
                result = ea.list_templates()
                display_result(result)

        with col2:
            with st.form("create_template"):
                t_name = st.text_input("Template Name")
                t_subject = st.text_input("Subject")
                t_body = st.text_area("Body")
                t_html = st.text_area("HTML Body (optional)")
                if st.form_submit_button("💾 Save Template"):
                    result = ea.create_template(
                        t_name, t_subject, t_body, t_html if t_html else None
                    )
                    display_result(result)

    with tab4:
        st.subheader("Bulk Email Send")
        st.info(
            "Upload a CSV with columns: email, subject, body (optional: html_body, cc, bcc)"
        )

        uploaded = st.file_uploader("Choose CSV file", type="csv")
        if uploaded:
            df = pd.read_csv(uploaded)
            st.dataframe(df.head())

            if st.button("📤 Send Bulk Emails"):
                emails = []
                for _, row in df.iterrows():
                    emails.append(
                        EmailMessage(
                            subject=row.get("subject", ""),
                            sender="",
                            recipients=[row["email"]] if "email" in row else [],
                            body=row.get("body", ""),
                            html_body=(
                                row.get("html_body") if "html_body" in row else None
                            ),
                            cc=[
                                c.strip()
                                for c in str(row.get("cc", "")).split(",")
                                if c.strip()
                            ],
                            bcc=[
                                b.strip()
                                for b in str(row.get("bcc", "")).split(",")
                                if b.strip()
                            ],
                        )
                    )

                progress = st.progress(0)
                result = ea.send_bulk_email(emails, delay=0.5)
                progress.progress(1.0)
                display_result(result)

    # Close connection on page change
    if st.button("🔌 Close Email Connection"):
        ea.close()
        st.success("Connection closed")


def render_reminders():
    """Render reminders interface."""
    st.header("⏰ Reminders & Calendar")

    rm = st.session_state.reminder_manager

    tab1, tab2, tab3 = st.tabs(
        ["➕ Create Reminder", "📋 View Reminders", "📅 Calendar Event"]
    )

    with tab1:
        st.subheader("Set New Reminder")
        with st.form("create_reminder"):
            title = st.text_input("Title", placeholder="Team meeting")
            description = st.text_area("Description", placeholder="Weekly team sync")

            col1, col2 = st.columns(2)
            with col1:
                date = st.date_input(
                    "Date", value=datetime.now().date() + timedelta(days=1)
                )
            with col2:
                time = st.time_input(
                    "Time", value=datetime.now().time().replace(hour=9, minute=0)
                )

            trigger_time = datetime.combine(date, time).isoformat()

            frequency = st.selectbox(
                "Frequency",
                options=[f.value for f in ReminderFrequency],
                format_func=lambda x: x.capitalize(),
            )

            if st.form_submit_button("⏰ Set Reminder"):
                result = rm.set_reminder(title, description, trigger_time, frequency)
                display_result(result)

    with tab2:
        st.subheader("All Reminders")

        col1, col2 = st.columns([3, 1])
        with col2:
            show_disabled = st.checkbox("Show disabled")

        if st.button("🔄 Refresh"):
            st.rerun()

        result = rm.list_reminders(include_disabled=show_disabled)
        if result.success and result.reminders:
            for reminder in result.reminders:
                with st.expander(
                    f"{'✅' if reminder.enabled else '❌'} {reminder.title} - {reminder.next_trigger or 'No next trigger'}"
                ):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.text(f"ID: {reminder.id}")
                        st.text(f"Frequency: {reminder.frequency.value}")
                    with col2:
                        st.text(f"Created: {reminder.created_at[:19]}")
                        st.text(
                            f"Last triggered: {reminder.last_triggered[:19] if reminder.last_triggered else 'Never'}"
                        )
                    with col3:
                        if reminder.enabled:
                            if st.button("Disable", key=f"disable_{reminder.id}"):
                                rm.enable_reminder(reminder.id, False)
                                st.rerun()
                        else:
                            if st.button("Enable", key=f"enable_{reminder.id}"):
                                rm.enable_reminder(reminder.id, True)
                                st.rerun()
                        if st.button(
                            "Delete", key=f"delete_{reminder.id}", type="secondary"
                        ):
                            rm.cancel_reminder(reminder.id)
                            st.rerun()

                    st.text(f"Description: {reminder.description}")
        else:
            st.info("No reminders found. Create one in the 'Create Reminder' tab.")

    with tab3:
        st.subheader("Create Calendar Event")
        with st.form("create_event"):
            evt_title = st.text_input("Event Title", placeholder="Project deadline")
            evt_description = st.text_area("Description")

            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date")
                start_time = st.time_input("Start Time")
            with col2:
                end_date = st.date_input("End Date", value=start_date)
                end_time = st.time_input(
                    "End Time", value=(datetime.now() + timedelta(hours=1)).time()
                )

            start_dt = datetime.combine(start_date, start_time).isoformat()
            end_dt = datetime.combine(end_date, end_time).isoformat()

            location = st.text_input("Location (optional)")

            if st.form_submit_button("📅 Create Event"):
                result = rm.set_calendar_event(
                    evt_title,
                    evt_description,
                    start_dt,
                    end_dt,
                    location if location else None,
                )
                display_result(result)


def render_followups():
    """Render the Follow-ups interface."""
    st.header("🔄 Follow-ups")
    st.caption("Manage customer follow-ups and track their progress")

    follow_up_service = st.session_state.follow_up_service

    # Load available customers for the selectbox
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    customers = customer_repo.list_customers(limit=1000)
    customer_options = {f"{c.name} ({c.customer_id})": c.customer_id for c in customers}
    customer_names = list(customer_options.keys())
    db.close()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["➕ Create Follow-up", "📋 Pending", "⏰ Upcoming", "✅ Completed"]
    )

    with tab1:
        st.subheader("Create New Follow-up")
        with st.form("create_followup"):
            col1, col2 = st.columns(2)
            with col1:
                if customer_names:
                    selected_customer = st.selectbox("Customer", options=customer_names, index=0)
                    customer_id = customer_options[selected_customer]
                else:
                    st.warning("No customers available. Please add customers first.")
                    customer_id = st.text_input("Customer ID", placeholder="CUST001", disabled=True)
                reason = st.text_area("Reason", placeholder="Reason for follow-up")
                due_date = st.date_input("Due Date", value=datetime.now().date() + timedelta(days=1))
            with col2:
                due_time = st.time_input("Due Time", value=datetime.now().time().replace(hour=10, minute=0))
                priority = st.slider("Priority", 0, 100, 50)
                status = st.selectbox("Status", ["pending", "in_progress", "waiting_approval", "completed", "cancelled"], index=0)

            next_action = st.text_area("Next Action (optional)")
            last_contact = st.text_input("Last Contact Date (optional, YYYY-MM-DD)")

            if st.form_submit_button("➕ Create Follow-up"):
                if not customer_id or not reason:
                    st.error("Customer ID and Reason are required")
                else:
                    try:
                        due_datetime = datetime.combine(
                            due_date,
                            due_time,
                            tzinfo=IST
                        )
                        follow_up = follow_up_service.create_follow_up(
                            customer_id=customer_id,
                            reason=reason,
                            due_date=due_datetime,
                            priority=priority,
                            next_action=next_action if next_action else None,
                        )
                        # Wrap FollowUp object for display_result compatibility
                        class FollowUpResult:
                            def __init__(self, fu):
                                self.success = True
                                self.message = f"Follow-up created for customer {fu.customer_id}"
                                self.follow_up = fu
                        display_result(FollowUpResult(follow_up))
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab2:
        st.subheader("Pending Follow-ups")
        if st.button("🔄 Refresh Pending"):
            st.rerun()

        follow_ups = follow_up_service.list_follow_ups(status="pending")
        if follow_ups:
            for fu in follow_ups:
                with st.expander(f"🔵 {fu.title} (Priority: {fu.priority}) - Due: {fu.due_date}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text(f"Customer ID: {fu.customer_id}")
                        st.text(f"Reason: {fu.reason}")
                    with col2:
                        st.text(f"Due: {fu.due_date}")
                        st.text(f"Priority: {fu.priority}")

                    st.text(f"Next Action: {fu.next_action or 'None'}")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Start", key=f"start_{fu.id}"):
                            result = follow_up_service.update_status(fu.id, "in_progress")
                            st.success(f"Status updated to in_progress")
                            st.rerun()
                    with col2:
                        if st.button("Complete", key=f"complete_{fu.id}"):
                            result = follow_up_service.update_status(fu.id, "completed")
                            st.success(f"Status updated to completed")
                            st.rerun()
                    with col3:
                        if st.button("Cancel", key=f"cancel_{fu.id}"):
                            result = follow_up_service.update_status(fu.id, "cancelled")
                            st.success(f"Status updated to cancelled")
                            st.rerun()
        else:
            st.info("No pending follow-ups")

    with tab3:
        st.subheader("Upcoming Follow-ups")
        if st.button("🔄 Refresh Upcoming"):
            st.rerun()

        follow_ups = follow_up_service.get_upcoming_follow_ups(days=7)
        if follow_ups:
            for fu in follow_ups:
                with st.expander(f"📅 {fu.title} (Priority: {fu.priority}) - Due: {fu.due_date}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text(f"Customer ID: {fu.customer_id}")
                        st.text(f"Reason: {fu.reason}")
                    with col2:
                        st.text(f"Due: {fu.due_date}")
                        st.text(f"Priority: {fu.priority}")

                    st.text(f"Next Action: {fu.next_action or 'None'}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Start", key=f"start_up_{fu.id}"):
                            result = follow_up_service.update_status(fu.id, "in_progress")
                            st.success(f"Status updated to in_progress")
                            st.rerun()
                    with col2:
                        if st.button("Complete", key=f"complete_up_{fu.id}"):
                            result = follow_up_service.update_status(fu.id, "completed")
                            st.success(f"Status updated to completed")
                            st.rerun()
        else:
            st.info("No upcoming follow-ups in the next 7 days")

    with tab4:
        st.subheader("Completed Follow-ups")
        if st.button("🔄 Refresh Completed"):
            st.rerun()

        follow_ups = follow_up_service.list_follow_ups(status="completed")
        if follow_ups:
            for fu in follow_ups:
                with st.expander(f"✅ {fu.title} - Completed: {fu.completed_at}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text(f"Customer ID: {fu.customer_id}")
                        st.text(f"Reason: {fu.reason}")
                    with col2:
                        st.text(f"Due: {fu.due_date}")
                        st.text(f"Completed: {fu.completed_at}")
                    st.text(f"Next Action: {fu.next_action or 'None'}")
        else:
            st.info("No completed follow-ups")

    # Overdue section
    st.divider()
    st.subheader("⚠️ Overdue Follow-ups")
    if st.button("🔄 Check Overdue"):
        st.rerun()

    overdue = follow_up_service.get_overdue_follow_ups()
    if overdue:
        for fu in overdue:
            with st.expander(f"🔴 {fu.title} - Was due: {fu.due_date}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.text(f"Customer ID: {fu.customer_id}")
                    st.text(f"Reason: {fu.reason}")
                with col2:
                    st.text(f"Was Due: {fu.due_date}")
                    st.text(f"Priority: {fu.priority}")

                st.text(f"Next Action: {fu.next_action or 'None'}")

                if st.button("Mark In Progress", key=f"overdue_{fu.id}"):
                    result = follow_up_service.update_status(fu.id, "in_progress")
                    st.success(f"Status updated to in_progress")
                    st.rerun()
    else:
        st.info("No overdue follow-ups")


def render_scheduled_workflows():
    """Render the Scheduled Workflows interface."""
    st.header("⏰ Scheduled Workflows")
    st.caption("Manage and monitor scheduled workflow executions")

    # Initialize session state for scheduled workflow service
    if "scheduled_workflow_engine" not in st.session_state:
        from src.services.scheduled_workflow import create_scheduled_workflow_engine
        st.session_state.scheduled_workflow_engine = create_scheduled_workflow_engine()

    engine = st.session_state.scheduled_workflow_engine

    tab1, tab2, tab3 = st.tabs(["➕ Create Workflow", "📋 Scheduled Workflows", "📜 Execution History"])

    with tab1:
        st.subheader("Create Scheduled Workflow")
        with st.form("create_scheduled_workflow"):
            col1, col2 = st.columns(2)
            with col1:
                workflow_id = st.text_input("Workflow ID", placeholder="daily_followup")
                workflow_name = st.text_input("Workflow Name", placeholder="Daily Follow-up Workflow")
                description = st.text_area("Description")
            with col2:
                frequency = st.selectbox(
                    "Frequency",
                    ["once", "daily", "weekly", "monthly", "cron"],
                    format_func=lambda x: x.capitalize()
                )
                max_runs = st.number_input("Max Runs (optional)", min_value=0, value=0, help="0 = unlimited")

            st.subheader("Schedule Configuration")
            col1, col2 = st.columns(2)
            with col1:
                if frequency in ["once", "daily"]:
                    run_time = st.time_input("Run Time", value=datetime.now().time().replace(hour=9, minute=0))
                elif frequency == "weekly":
                    day_of_week = st.selectbox("Day of Week", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                    run_time = st.time_input("Run Time", value=datetime.now().time().replace(hour=9, minute=0))
                elif frequency == "monthly":
                    day_of_month = st.number_input("Day of Month", min_value=1, max_value=28, value=1)
                    run_time = st.time_input("Run Time", value=datetime.now().time().replace(hour=9, minute=0))
                else:
                    cron_expression = st.text_input("Cron Expression", placeholder="0 9 * * *")

            st.subheader("Workflow Plan (JSON)")
            workflow_plan_json = st.text_area(
                "Workflow Plan",
                value=json.dumps({
                    "workflow_type": "customer_followup",
                    "name": "Scheduled Follow-up",
                    "description": "Automated follow-up workflow",
                    "target_customers": {"segment": "inactive_customer"},
                    "steps": [
                        {"step_id": "step_1", "action": "customer_search", "description": "Find inactive customers", "parameters": {"segment": "inactive_customer"}},
                        {"step_id": "step_2", "action": "customer_analysis", "description": "Analyze customers", "parameters": {"use_ai": True}},
                        {"step_id": "step_3", "action": "create_task", "description": "Create follow-up tasks", "parameters": {"title": "Follow up with inactive customer", "task_type": "follow_up"}},
                    ]
                }, indent=2),
                height=200
            )

            if st.form_submit_button("⏰ Create Scheduled Workflow"):
                try:
                    schedule_config = {"time": run_time.strftime("%H:%M")}
                    if frequency == "weekly":
                        schedule_config["day_of_week"] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(day_of_week)
                    elif frequency == "monthly":
                        schedule_config["day_of_month"] = day_of_month
                    elif frequency == "cron":
                        schedule_config["cron_expression"] = cron_expression

                    workflow_plan = json.loads(workflow_plan_json)

                    from src.core.workflow_models import WorkflowPlan
                    from src.db.models import ScheduledWorkflowFrequency
                    from src.services.scheduled_workflow import create_scheduled_workflow_engine

                    engine = create_scheduled_workflow_engine()
                    workflow = engine.create_scheduled_workflow(
                        workflow_id=workflow_id,
                        workflow_name=workflow_name,
                        description=description,
                        frequency=ScheduledWorkflowFrequency(frequency),
                        schedule_config=schedule_config,
                        workflow_plan=workflow_plan,
                    )
                    st.success(f"Created scheduled workflow: {workflow.workflow_id}")
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab2:
        st.subheader("Scheduled Workflows")
        if st.button("🔄 Refresh"):
            st.rerun()

        try:
            engine = create_scheduled_workflow_engine()
            workflows = engine.list_workflows()
            if workflows:
                for w in workflows:
                    status_color = {"active": "🟢", "paused": "🟡", "disabled": "🔴", "completed": "✅"}.get(w.status.value, "⚪")
                    with st.expander(f"{status_color} {w.workflow_name} ({w.frequency.value}) - Next: {w.next_run or 'N/A'}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.text(f"Workflow ID: {w.workflow_id}")
                            st.text(f"Status: {w.status.value}")
                            st.text(f"Run Count: {w.run_count}")
                        with col2:
                            st.text(f"Next Run: {w.next_run or 'N/A'}")
                            st.text(f"Last Run: {w.last_run or 'N/A'}")
                            st.text(f"Last Status: {w.last_run_status or 'N/A'}")

                        st.text(f"Description: {w.description or 'None'}")

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            if w.status != "paused":
                                if st.button("Pause", key=f"pause_{w.id}"):
                                    from src.services.scheduled_workflow import create_scheduled_workflow_engine
                                    engine = create_scheduled_workflow_engine()
                                    engine.pause_workflow(w.workflow_id)
                                    st.success("Workflow paused")
                                    st.rerun()
                        with col2:
                            if w.status == "paused":
                                if st.button("Resume", key=f"resume_{w.id}"):
                                    from src.services.scheduled_workflow import create_scheduled_workflow_engine
                                    engine = create_scheduled_workflow_engine()
                                    engine.resume_workflow(w.workflow_id)
                                    st.success("Workflow resumed")
                                    st.rerun()
                        with col3:
                            if st.button("Run Now", key=f"run_{w.id}"):
                                from src.services.scheduled_workflow import create_scheduled_workflow_engine
                                engine = create_scheduled_workflow_engine()
                                engine.execute_workflow(w)
                                st.success("Workflow executed")
                                st.rerun()
                        with col4:
                            if st.button("Disable", key=f"disable_{w.id}"):
                                from src.services.scheduled_workflow import create_scheduled_workflow_engine
                                engine = create_scheduled_workflow_engine()
                                engine.disable_workflow(w.workflow_id)
                                st.success("Workflow disabled")
                                st.rerun()
            else:
                st.info("No scheduled workflows. Create one in the 'Create Workflow' tab.")
        except Exception as e:
            st.error(f"Error loading workflows: {e}")

    with tab3:
        st.subheader("Execution History")
        if st.button("🔄 Refresh History"):
            st.rerun()

        try:
            engine = create_scheduled_workflow_engine()
            workflows = engine.list_workflows()
            if workflows:
                selected_workflow = st.selectbox(
                    "Select Workflow",
                    workflows,
                    format_func=lambda w: f"{w.workflow_name} ({w.workflow_id})"
                )
                if selected_workflow:
                    executions = engine.get_workflow_executions(selected_workflow.workflow_id, limit=50)
                    if executions:
                        for exec in executions:
                            status_icon = {"running": "🔄", "completed": "✅", "failed": "❌"}.get(exec.status, "❓")
                            with st.expander(f"{status_icon} {exec.execution_id} - {exec.status} - {exec.started_at}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.text(f"Started: {exec.started_at}")
                                    st.text(f"Completed: {exec.completed_at or 'N/A'}")
                                with col2:
                                    st.text(f"Customers: {exec.customers_processed}")
                                    st.text(f"Actions: {exec.actions_executed}")

                                if exec.errors:
                                    st.error(f"Errors: {exec.errors}")
                                if exec.result_summary:
                                    st.text(f"Summary: {exec.result_summary}")
                    else:
                        st.info("No executions yet for this workflow")
            else:
                st.info("No scheduled workflows to show history for")
        except Exception as e:
            st.error(f"Error loading execution history: {e}")


def render_customer_dashboard():
    """Render the Customer Dashboard interface."""
    st.header("👥 Customer Dashboard")
    st.caption("Overview of all customers with key metrics and insights")

    # Refresh button
    if st.button("🔄 Refresh Dashboard"):
        st.rerun()

    # Get stats from database
    db = next(get_db())
    repo = CustomerRepository(db)
    stats = repo.get_dashboard_stats()
    db.close()

    # Overview metrics
    st.subheader("📈 Overview")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Customers", stats.get("total_customers", 0))
    with col2:
        st.metric("Active Customers", stats.get("active_customers", 0))
    with col3:
        st.metric("High-Value Customers", stats.get("high_value_customers", 0))
    with col4:
        st.metric("At-Risk Customers", stats.get("at_risk_customers", 0))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Payment Risk", stats.get("payment_risk_customers", 0))
    with col2:
        st.metric("Overdue Payments", stats.get("overdue_payments", 0))
    with col3:
        st.metric("Customers Needing Follow-up", stats.get("customers_needing_followup", 0))
    with col4:
        st.metric("Pending Approvals", stats.get("pending_approvals", 0))

    st.divider()

    # Segment distribution
    st.subheader("📊 Customer Segments")
    db = next(get_db())
    repo = CustomerRepository(db)
    segment_dist = repo.get_segment_distribution()
    db.close()

    if segment_dist:
        seg_col1, seg_col2 = st.columns(2)
        with seg_col1:
            for segment, count in segment_dist.items():
                seg_info = CUSTOMER_SEGMENTS.get(segment, {"name": segment.replace("_", " ").title(), "color": "#1f77b4"})
                st.markdown(f"""
                <div style="padding: 10px; border-radius: 5px; background-color: {seg_info['color']}20; border-left: 4px solid {seg_info['color']};">
                    <strong>{seg_info['name']}</strong><br>
                    Count: {count}
                </div>
                """, unsafe_allow_html=True)
        with seg_col2:
            st.bar_chart(segment_dist)
    else:
        st.info("No customer data available. Import customers first.")

    st.divider()

    # Quick actions
    st.subheader("⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔍 Find Customers Needing Follow-up", use_container_width=True):
            st.session_state.mode = "🔍 Customer Analysis"
            st.rerun()
    with col2:
        if st.button("📧 Send Re-engagement Emails", use_container_width=True):
            st.session_state.mode = "📧 Email Automation"
            st.rerun()
    with col3:
        if st.button("📊 Generate Customer Report", use_container_width=True):
            st.session_state.mode = "📊 Customer Segmentation"
            st.rerun()


def render_customer_analysis():
    """Render the Customer Analysis interface."""
    st.header("🔍 Customer Analysis")
    st.caption("Analyze individual customers or batches with AI-powered insights")

    tab1, tab2, tab3 = st.tabs(["🔍 Single Customer", "📦 Batch Analysis", "💡 Insights & Recommendations"])

    with tab1:
        st.subheader("Analyze Individual Customer")
        with st.form("analyze_customer_form"):
            customer_id = st.text_input("Customer ID", placeholder="CUST001")
            use_ai = st.checkbox("Use AI for deeper analysis", value=True)
            
            if st.form_submit_button("🔍 Analyze Customer"):
                if not customer_id:
                    st.error("Customer ID is required")
                else:
                    db = next(get_db())
                    repo = CustomerRepository(db)
                    customer = repo.get_by_customer_id(customer_id)
                    db.close()
                    
                    if not customer:
                        st.error(f"Customer {customer_id} not found")
                    else:
                        intelligence = create_customer_intelligence()
                        analysis = intelligence.analyze_customer(customer, use_ai=use_ai)
                        
                        if analysis:
                            st.success(f"Analysis complete for {customer.name}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Engagement Score", f"{analysis.engagement_score.normalized:.0%}")
                                st.metric("Value Score", f"{analysis.value_score.normalized:.0%}")
                            with col2:
                                st.metric("Churn Risk", f"{analysis.churn_risk.normalized:.0%}")
                                st.metric("Follow-up Priority", f"{analysis.follow_up_priority.normalized:.0%}")
                            
                            st.info(f"**Segment**: {analysis.segment.value.replace('_', ' ').title()}")
                            st.info(f"**Reasoning**: {analysis.segment_reasoning}")
                            st.info(f"**Recommended Action**: {analysis.recommended_action}")
                            st.info(f"**Recommended Communication**: {analysis.recommended_communication_type}")
                            st.info(f"**Priority**: {analysis.priority}/100")
                            st.info(f"**Confidence**: {analysis.confidence:.0%}")
                        else:
                            st.error("Analysis failed")

    with tab2:
        st.subheader("Batch Customer Analysis")
        with st.form("batch_analysis_form"):
            customer_ids_text = st.text_area("Customer IDs (one per line)", placeholder="CUST001\nCUST002\nCUST003")
            use_ai = st.checkbox("Use AI for deeper analysis", value=False)
            
            if st.form_submit_button("📦 Analyze Batch"):
                if not customer_ids_text.strip():
                    st.error("Please enter at least one customer ID")
                else:
                    customer_ids = [cid.strip() for cid in customer_ids_text.split("\n") if cid.strip()]
                    
                    db = next(get_db())
                    repo = CustomerRepository(db)
                    
                    customers = []
                    for cid in customer_ids:
                        customer = repo.get_by_customer_id(cid)
                        if customer:
                            customers.append(customer)
                    
                    db.close()
                    
                    if not customers:
                        st.error("No valid customers found")
                    else:
                        intelligence = create_customer_intelligence()
                        analyses = intelligence.batch_analyze(customers, use_ai=use_ai)
                        
                        st.success(f"Analyzed {len(analyses)} customers")
                        
                        # Display results
                        for analysis in analyses:
                            with st.expander(f"{analysis.customer_id} - {analysis.segment.value}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("Engagement", f"{analysis.engagement_score.normalized:.0%}")
                                    st.metric("Value", f"{analysis.value_score.normalized:.0%}")
                                with col2:
                                    st.metric("Churn Risk", f"{analysis.churn_risk.normalized:.0%}")
                                    st.metric("Priority", f"{analysis.follow_up_priority.normalized:.0%}")
                                st.text(f"Action: {analysis.recommended_action}")

    with tab3:
        st.subheader("💡 Insights & Recommendations")
        
        if st.button("🔍 Generate Insights for All Customers"):
            with st.spinner("Analyzing all customers..."):
                db = next(get_db())
                repo = CustomerRepository(db)
                customers = repo.list_customers(limit=500)
                db.close()
                
                if not customers:
                    st.info("No customers to analyze")
                else:
                    intelligence = create_customer_intelligence()
                    analyzer = create_customer_analyzer()
                    
                    insights = []
                    for customer in customers:
                        cust_insights = analyzer.generate_insights(customer)
                        insights.extend(cust_insights)
                    
                    if insights:
                        st.success(f"Generated {len(insights)} insights")
                        
                        # Group by type
                        by_type = {}
                        for i in insights:
                            if i.insight_type not in by_type:
                                by_type[i.insight_type] = []
                            by_type[i.insight_type].append(i)
                        
                        for insight_type, type_insights in by_type.items():
                            with st.expander(f"{insight_type.title()} ({len(type_insights)})"):
                                for insight in type_insights[:10]:  # Show top 10
                                    st.markdown(f"""
                                    **{insight.title}** (Priority: {insight.priority.name})
                                    - Customer: {insight.customer_id}
                                    - {insight.description}
                                    - Actions: {', '.join(insight.suggested_actions)}
                                    """)
                    else:
                        st.info("No insights generated")


def render_customer_segmentation():
    """Render the Customer Segmentation interface."""
    st.header("📊 Customer Segmentation")
    st.caption("View and manage customer segments with AI-powered classification")

    tab1, tab2 = st.tabs(["📊 Segment Overview", "🔧 Manage Segments"])

    with tab1:
        st.subheader("Segment Distribution")
        
        db = next(get_db())
        repo = CustomerRepository(db)
        segment_dist = repo.get_segment_distribution()
        db.close()
        
        if segment_dist:
            col1, col2 = st.columns([1, 2])
            with col1:
                for segment, count in segment_dist.items():
                    seg_info = CUSTOMER_SEGMENTS.get(segment, {"name": segment.replace("_", " ").title(), "color": "#1f77b4"})
                    st.markdown(f"""
                    <div style="padding: 15px; border-radius: 8px; background-color: {seg_info['color']}15; border-left: 5px solid {seg_info['color']}; margin: 10px 0;">
                        <strong style="font-size: 1.1em;">{seg_info['name']}</strong><br>
                        <span style="font-size: 1.5em; font-weight: bold;">{count}</span> customers
                    </div>
                    """, unsafe_allow_html=True)
            with col2:
                import pandas as pd
                df = pd.DataFrame(list(segment_dist.items()), columns=["Segment", "Count"])
                st.bar_chart(df.set_index("Segment"))
        else:
            st.info("No customer data available")

    with tab2:
        st.subheader("Segment Management")
        
        for segment_key, seg_info in CUSTOMER_SEGMENTS.items():
            with st.expander(f"{seg_info['name']} ({segment_key})"):
                st.markdown(f"**Description**: {seg_info['description']}")
                st.markdown(f"**Criteria**: {seg_info['criteria']}")
                
                if st.button(f"🔄 Re-segment {seg_info['name']}", key=f"resegment_{segment_key}"):
                    with st.spinner(f"Re-segmenting {seg_info['name']}..."):
                        db = next(get_db())
                        repo = CustomerRepository(db)
                        intelligence = create_customer_intelligence()
                        
                        # Get customers in this segment
                        filters = {"segment": segment_key}
                        customers = repo.list_customers(filters=filters, limit=1000)
                        db.close()
                        
                        if customers:
                            analyses = intelligence.batch_analyze(customers, use_ai=False)
                            
                            # Update segments
                            for customer, analysis in zip(customers, analyses):
                                if analysis.segment.value != segment_key:
                                    customer.customer_segment = analysis.segment
                                    customer.updated_at = datetime.now()
                                    db = next(get_db())
                                    repo = CustomerRepository(db)
                                    repo.update(customer)
                                    db.close()
                            
                            st.success(f"Re-segmented {len(customers)} customers")
                            st.rerun()
                        else:
                            st.info("No customers in this segment")

    st.divider()
    
    # Bulk re-segmentation
    st.subheader("🔄 Bulk Re-segmentation")
    if st.button("🔄 Re-segment All Customers", use_container_width=True):
        with st.spinner("Analyzing all customers..."):
            db = next(get_db())
            repo = CustomerRepository(db)
            intelligence = create_customer_intelligence()
            
            customers = repo.list_customers(limit=5000)
            db.close()
            
            if customers:
                analyses = intelligence.batch_analyze(customers, use_ai=False)
                
                updated = 0
                for customer, analysis in zip(customers, analyses):
                    if customer.customer_segment != analysis.segment:
                        db = next(get_db())
                        repo = CustomerRepository(db)
                        customer.customer_segment = analysis.segment
                        customer.segment_reasoning = analysis.segment_reasoning
                        customer.updated_at = datetime.now()
                        repo.update(customer)
                        db.close()
                        updated += 1
                
                st.success(f"Updated {updated} customer segments")
                st.rerun()


if __name__ == "__main__":
    main()
