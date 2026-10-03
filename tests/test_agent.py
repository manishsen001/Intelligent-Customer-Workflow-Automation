"""Tests for the agent module."""

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing (must be done before importing settings)
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.agents.base_agent import (
    WorkflowType,
    AgentResponse,
    WorkflowAgent,
    create_agent,
    check_llm_connection,
)


def test_workflow_type_enum():
    """Test WorkflowType enum values."""
    assert WorkflowType.TASK_AUTOMATION.value == "task_automation"
    assert WorkflowType.EMAIL_AUTOMATION.value == "email_automation"
    assert WorkflowType.REMINDER.value == "reminder"
    assert WorkflowType.UNKNOWN.value == "unknown"


def test_agent_response_dataclass():
    """Test AgentResponse dataclass creation."""
    response = AgentResponse(
        workflow_type=WorkflowType.TASK_AUTOMATION,
        action="run_script",
        parameters={"script_path": "test.py"},
        confidence=0.9,
        reasoning="Test reasoning",
    )
    assert response.workflow_type == WorkflowType.TASK_AUTOMATION
    assert response.action == "run_script"
    assert response.confidence == 0.9


def test_create_agent():
    """Test agent factory function."""
    agent = create_agent()
    assert isinstance(agent, WorkflowAgent)
    assert agent.model is not None


def test_workflow_agent_prompts():
    """Test WorkflowAgent has required prompts and actions."""
    agent = create_agent()
    system_prompt = agent.get_system_prompt()
    actions = agent.get_available_actions()
    
    assert isinstance(system_prompt, str)
    assert len(system_prompt) > 0
    assert isinstance(actions, list)
    # Now we have 11 workflow types (10 customer/automation + 1 unknown for informational)
    assert len(actions) == 11
    
    workflow_types = {a["workflow_type"] for a in actions}
    expected_types = {
        "customer_followup", "inactive_reengagement", "high_value_outreach",
        "payment_collection", "support_followup", "new_lead_qualification",
        "custom", "task_automation", "email_automation", "reminder",
        "unknown"
    }
    assert workflow_types == expected_types


def test_check_llm_connection_no_key():
    """Test connection check with missing API key."""
    # Temporarily clear the API key
    from src.config import settings as settings_module
    original_key = settings_module.settings.NVIDIA_API_KEY
    settings_module.settings.NVIDIA_API_KEY = ""
    
    try:
        success, message = check_llm_connection()
        assert success is False
        assert "API_KEY" in message or "Missing" in message
    finally:
        settings_module.settings.NVIDIA_API_KEY = original_key


def test_unknown_workflow_actions():
    """Test that UNKNOWN workflow type has provide_information and ask_clarification actions."""
    agent = create_agent()
    actions = agent.get_available_actions()
    
    unknown_actions = next(a for a in actions if a["workflow_type"] == "unknown")
    action_names = {a["name"] for a in unknown_actions["actions"]}
    
    assert "provide_information" in action_names
    assert "ask_clarification" in action_names
    
    # Verify descriptions are present
    provide_info = next(a for a in unknown_actions["actions"] if a["name"] == "provide_information")
    ask_clarify = next(a for a in unknown_actions["actions"] if a["name"] == "ask_clarification")
    assert "informational" in provide_info["description"].lower()
    assert "clarification" in ask_clarify["description"].lower()


def test_informational_request_routing():
    """Test that informational requests are routed to provide_information."""
    # This test verifies the agent classifies informational requests correctly
    # We mock the LLM call to avoid network dependency
    from unittest.mock import patch, MagicMock
    
    agent = create_agent()
    
    # Mock the LLM response for informational request
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "workflow_type": "unknown",
        "action": "provide_information",
        "parameters": {},
        "confidence": 1.0,
        "reasoning": "This is an informational request about capabilities."
    })
    
    with patch.object(agent.client.chat.completions, 'create', return_value=mock_response):
        response = agent.process("Explain what you can automate.")
        
    assert response.workflow_type == WorkflowType.UNKNOWN
    assert response.action == "provide_information"
    assert "informational" in response.reasoning.lower()


def test_ambiguous_request_routing():
    """Test that ambiguous requests are routed to ask_clarification."""
    from unittest.mock import patch, MagicMock
    import json
    
    agent = create_agent()
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "workflow_type": "unknown",
        "action": "ask_clarification",
        "parameters": {},
        "confidence": 0.9,
        "reasoning": "Please clarify what you want to do."
    })
    
    with patch.object(agent.client.chat.completions, 'create', return_value=mock_response):
        response = agent.process("Do something vague.")
        
    assert response.workflow_type == WorkflowType.UNKNOWN
    assert response.action == "ask_clarification"
    assert "clarif" in response.reasoning.lower()


def test_automation_request_routing():
    """Test that valid automation requests are routed to appropriate workflows."""
    from unittest.mock import patch, MagicMock
    import json
    
    agent = create_agent()
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "workflow_type": "reminder",
        "action": "set_reminder",
        "parameters": {"trigger_time": "2025-01-15T17:00:00", "message": "Test"},
        "confidence": 0.95,
        "reasoning": "Setting a reminder."
    })
    
    with patch.object(agent.client.chat.completions, 'create', return_value=mock_response):
        response = agent.process("Set a reminder for tomorrow.")
        
    assert response.workflow_type == WorkflowType.REMINDER
    assert response.action == "set_reminder"


if __name__ == "__main__":
    test_workflow_type_enum()
    test_agent_response_dataclass()
    test_create_agent()
    test_workflow_agent_prompts()
    test_unknown_workflow_actions()
    test_informational_request_routing()
    test_ambiguous_request_routing()
    test_automation_request_routing()
    test_check_llm_connection_no_key()
    print("All agent tests passed!")