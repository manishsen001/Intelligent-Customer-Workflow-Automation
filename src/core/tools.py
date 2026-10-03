"""Tool interfaces and registry for Customer Workflow Automation System."""

import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.config.logging_config import logger
from src.core.workflow_models import ToolResult, ToolSchema, WorkflowExecutionContext


class BaseTool(ABC):
    """Base class for all workflow tools."""
    
    def __init__(self):
        self.description = self._get_description()
        self.schema = self._get_schema()
        self.name = self.schema.name
    
    @abstractmethod
    def _get_description(self) -> str:
        """Return tool description."""
        pass
    
    @abstractmethod
    def _get_schema(self) -> ToolSchema:
        """Return tool input schema."""
        pass
    
    def validate_input(self, parameters: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate input parameters against schema."""
        for param in self.schema.parameters:
            if param.required and param.name not in parameters:
                return False, f"Required parameter '{param.name}' is missing"
            if param.name in parameters:
                value = parameters[param.name]
                if param.type == "string" and not isinstance(value, str):
                    return False, f"Parameter '{param.name}' must be a string"
                if param.type == "integer" and not isinstance(value, int):
                    return False, f"Parameter '{param.name}' must be an integer"
                if param.type == "number" and not isinstance(value, (int, float)):
                    return False, f"Parameter '{param.name}' must be a number"
                if param.type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter '{param.name}' must be a boolean"
                if param.type == "array" and not isinstance(value, list):
                    return False, f"Parameter '{param.name}' must be an array"
                if param.type == "object" and not isinstance(value, dict):
                    return False, f"Parameter '{param.name}' must be an object"
                if param.enum and value not in param.enum:
                    return False, f"Parameter '{param.name}' must be one of: {param.enum}"
        return True, None
    
    def execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        """Execute the tool with validation and error handling."""
        start_time = time.time()
        
        # Validate input
        valid, error = self.validate_input(parameters)
        if not valid:
            return ToolResult(
                success=False,
                error=error,
                execution_time=time.time() - start_time,
            )
        
        try:
            result = self._execute(context, parameters)
            execution_time = time.time() - start_time
            if not isinstance(result, ToolResult):
                result = ToolResult(success=True, data=result, execution_time=execution_time)
            else:
                result.execution_time = execution_time
            logger.info(f"Tool {self.name} executed successfully in {execution_time:.3f}s")
            return result
        except Exception as e:
            logger.error(f"Tool {self.name} execution failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time,
            )
    
    @abstractmethod
    def _execute(self, context: WorkflowExecutionContext, parameters: dict[str, Any]) -> ToolResult:
        """Execute the tool logic. Must be implemented by subclasses."""
        pass


class ToolRegistry:
    """Registry for managing and discovering tools."""
    
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool: {name}")
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def get_schemas(self) -> list[dict]:
        """Get all tool schemas for AI function calling."""
        return [tool.schema.to_dict() for tool in self._tools.values()]
    
    def get_tool_names(self) -> list[str]:
        """Get list of tool names."""
        return list(self._tools.keys())
    
    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools


# Global tool registry
tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return tool_registry