"""Tests for workflow planner and tools."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
import os
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.core.workflow_models import (
    WorkflowPlan,
    WorkflowStep,
    WorkflowType,
    ActionType,
    ApprovalRequired,
    ToolResult,
    ToolParameter,
    ToolSchema,
)
from src.core.tools import BaseTool, ToolRegistry, tool_registry, get_tool_registry
from src.core.workflow_planner import WorkflowPlanner, create_workflow_planner


def test_tool_schema():
    """Test ToolSchema generation."""
    schema = ToolSchema(
        name="test_tool",
        description="A test tool",
        parameters=[
            ToolParameter("param1", "string", "First parameter", required=True),
            ToolParameter("param2", "integer", "Second parameter", required=False, default=10),
            ToolParameter("param3", "string", "Third parameter with enum", required=False, enum=["a", "b", "c"]),
        ]
    )
    
    d = schema.to_dict()
    # New format: OpenAI function calling format
    assert d["name"] == "test_tool"
    assert d["description"] == "A test tool"
    assert "parameters" in d
    assert d["parameters"]["type"] == "object"
    assert "param1" in d["parameters"]["properties"]
    assert d["parameters"]["properties"]["param1"]["type"] == "string"
    assert d["parameters"]["properties"]["param2"]["type"] == "integer"
    assert d["parameters"]["properties"]["param2"]["default"] == 10
    assert "param1" in d["parameters"]["required"]
    assert "param2" not in d["parameters"]["required"]
    assert d["parameters"]["properties"]["param3"]["enum"] == ["a", "b", "c"]
    
    print("✓ ToolSchema tests passed")


def test_workflow_step():
    """Test WorkflowStep creation."""
    step = WorkflowStep(
        step_id="step_1",
        action=ActionType.CUSTOMER_SEARCH,
        description="Find inactive customers",
        parameters={"segment": "inactive_customer", "limit": 50},
        depends_on=[],
        approval_required=ApprovalRequired.NONE,
    )
    
    assert step.step_id == "step_1"
    assert step.action == ActionType.CUSTOMER_SEARCH
    assert step.parameters["segment"] == "inactive_customer"
    
    print("✓ WorkflowStep tests passed")


def test_workflow_plan():
    """Test WorkflowPlan creation and serialization."""
    steps = [
        WorkflowStep(
            step_id="step_1",
            action=ActionType.CUSTOMER_SEARCH,
            description="Find inactive customers",
            parameters={"segment": "inactive_customer"},
        ),
        WorkflowStep(
            step_id="step_2",
            action=ActionType.CUSTOMER_ANALYSIS,
            description="Analyze found customers",
            parameters={"use_ai": True},
            depends_on=["step_1"],
        ),
    ]
    
    plan = WorkflowPlan(
        plan_id="test_plan_123",
        workflow_type=WorkflowType.INACTIVE_REENGAGEMENT,
        name="Inactive Customer Re-engagement",
        description="Re-engage customers inactive for 30+ days",
        target_customers={"segment": "inactive_customer", "days_inactive": 30},
        steps=steps,
        approval_required=ApprovalRequired.REQUIRED,
    )
    
    # Test serialization
    plan_dict = plan.to_dict()
    assert plan_dict["plan_id"] == "test_plan_123"
    assert plan_dict["workflow_type"] == "inactive_reengagement"
    assert len(plan_dict["steps"]) == 2
    assert plan_dict["steps"][1]["depends_on"] == ["step_1"]
    
    # Test deserialization
    plan2 = WorkflowPlan.from_dict(plan_dict)
    assert plan2.plan_id == plan.plan_id
    assert plan2.workflow_type == plan.workflow_type
    assert len(plan2.steps) == 2
    assert plan2.steps[1].depends_on == ["step_1"]
    
    print("✓ WorkflowPlan tests passed")


def test_tool_registry():
    """Test ToolRegistry operations."""
    registry = ToolRegistry()
    
    # Create a mock tool
    class MockTool(BaseTool):
        def _get_description(self):
            return "Mock tool for testing"
        
        def _get_schema(self):
            return ToolSchema(
                name="mock_tool",
                description="Mock tool for testing",
                parameters=[ToolParameter("input", "string", "Test input", required=True)],
            )
        
        def _execute(self, context, parameters):
            return ToolResult(success=True, data={"echo": parameters["input"]})
    
    tool = MockTool()
    registry.register(tool)
    
    assert registry.has_tool("mock_tool")
    assert registry.get("mock_tool") == tool
    assert len(registry.list_tools()) == 1
    assert "mock_tool" in registry.get_tool_names()
    
    schema_list = registry.get_schemas()
    assert len(schema_list) == 1
    assert schema_list[0]["name"] == "mock_tool"
    
    registry.unregister("mock_tool")
    assert not registry.has_tool("mock_tool")
    
    print("✓ ToolRegistry tests passed")


def test_tool_result():
    """Test ToolResult creation."""
    result = ToolResult(
        success=True,
        data={"key": "value"},
        execution_time=0.5,
        metadata={"source": "test"},
    )
    
    assert result.success is True
    assert result.data == {"key": "value"}
    assert result.execution_time == 0.5
    
    d = result.to_dict()
    assert d["success"] is True
    assert d["data"] == {"key": "value"}
    
    # Test error result
    error_result = ToolResult(success=False, error="Something went wrong")
    assert error_result.success is False
    assert error_result.error == "Something went wrong"
    
    print("✓ ToolResult tests passed")


def test_workflow_planner_creation():
    """Test workflow planner can be created."""
    planner = create_workflow_planner()
    assert planner is not None
    assert isinstance(planner, WorkflowPlanner)
    assert planner.registry is not None
    
    # Check tools are registered
    tool_names = planner.registry.get_tool_names()
    expected_tools = [
        "customer_search",
        "customer_analysis",
        "create_task",
        "generate_email",
        "send_email",
        "create_reminder",
        "schedule_workflow",
        "customer_report",
    ]
    for tool in expected_tools:
        assert tool in tool_names, f"Missing tool: {tool}"
    
    print("✓ WorkflowPlanner creation tests passed")


def test_tool_parameter_validation():
    """Test tool parameter validation."""
    class ValidationTool(BaseTool):
        def _get_description(self):
            return "Tool with validation"
        
        def _get_schema(self):
            return ToolSchema(
                name="validation_tool",
                description="Tool with validation",
                parameters=[
                    ToolParameter("required_str", "string", "Required string", required=True),
                    ToolParameter("optional_int", "integer", "Optional integer", required=False, default=5),
                    ToolParameter("enum_param", "string", "Enum parameter", required=False, enum=["a", "b", "c"]),
                ]
            )
        
        def _execute(self, context, parameters):
            return ToolResult(success=True, data=parameters)
    
    tool = ValidationTool()
    
    # Valid input
    valid, error = tool.validate_input({"required_str": "test", "optional_int": 10, "enum_param": "a"})
    assert valid is True
    assert error is None
    
    # Missing required
    valid, error = tool.validate_input({"optional_int": 10})
    assert valid is False
    assert "required_str" in error
    
    # Invalid type
    valid, error = tool.validate_input({"required_str": "test", "optional_int": "not_an_int"})
    assert valid is False
    assert "must be an integer" in error
    
    # Invalid enum
    valid, error = tool.validate_input({"required_str": "test", "enum_param": "invalid"})
    assert valid is False
    assert "must be one of" in error
    
    print("✓ Tool parameter validation tests passed")


if __name__ == "__main__":
    test_tool_schema()
    test_workflow_step()
    test_workflow_plan()
    test_tool_registry()
    test_tool_result()
    test_workflow_planner_creation()
    test_tool_parameter_validation()
    print("\n✅ All workflow planner tests passed!")