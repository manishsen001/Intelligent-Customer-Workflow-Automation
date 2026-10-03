"""Workflow planner for converting natural language to structured workflow plans."""

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from openai import OpenAI

from src.config.logging_config import logger
from src.config.settings import settings
from src.core.tools import tool_registry, get_tool_registry
from src.core.workflow_models import (
    WorkflowPlan,
    WorkflowStep,
    WorkflowType,
    ActionType,
    ApprovalRequired,
    WorkflowExecutionContext,
    ToolResult,
)
from src.db.models import ApprovalStatus


class WorkflowPlanner:
    """AI-powered workflow planner that converts natural language to structured plans."""
    
    def __init__(self):
        self._llm_client: Optional[OpenAI] = None
        self.registry = get_tool_registry()
    
    def _get_llm_client(self) -> OpenAI:
        if self._llm_client is None:
            llm_config = settings.get_llm_config()
            self._llm_client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"],
            )
        return self._llm_client
    
    def _get_available_tools_description(self) -> str:
        """Get description of available tools for the AI."""
        tools = self.registry.list_tools()
        descriptions = []
        for tool in tools:
            params = []
            for p in tool.schema.parameters:
                req = " (required)" if p.required else " (optional)"
                enum_str = f" - enum: {p.enum}" if p.enum else ""
                params.append(f"  - {p.name} ({p.type}){req}: {p.description}{enum_str}")
            descriptions.append(
                f"Tool: {tool.name}\n"
                f"  Description: {tool.description}\n"
                f"  Parameters:\n" + "\n".join(params)
            )
        return "\n\n".join(descriptions)
    
    def _get_workflow_types_description(self) -> str:
        """Get description of workflow types."""
        return """
Workflow Types:
- customer_followup: General customer follow-up based on various triggers
- inactive_reengagement: Re-engage inactive customers with personalized outreach
- high_value_outreach: Proactive outreach to high-value customers
- payment_collection: Follow up on overdue payments
- support_followup: Follow up on open support issues
- new_lead_qualification: Qualify and nurture new leads
- custom: Custom workflow defined by user
"""
    
    def create_plan_from_natural_language(
        self,
        user_request: str,
        context: Optional[dict] = None,
    ) -> WorkflowPlan:
        """Convert natural language request to a structured workflow plan."""
        
        client = self._get_llm_client()
        tools_desc = self._get_available_tools_description()
        workflow_types_desc = self._get_workflow_types_description()
        
        system_prompt = """You are a Customer Workflow Planner. Convert the user's natural language request into a structured workflow plan.

Available Tools:
{tools_desc}

{workflow_types_desc}

The user will describe what they want to accomplish. You must:
1. Identify the workflow type
2. Determine the target customer criteria
3. Plan a sequence of tool calls (steps)
4. Specify any approval requirements
5. Return a valid JSON workflow plan

Rules:
- Each step must use a registered tool
- Steps can depend on previous steps (use step_id in depends_on)
- Use customer_search first to identify target customers
- Use customer_analysis to score/segment customers before actions
- IMPORTANT: When using customer_analysis after customer_search, you MUST include "customer_ids" parameter referencing the previous step's results using the format: {{"customer_ids": "{{step_X.result.customer_ids"}}} where X is the step_id of the customer_search step. NOTE: Use DOUBLE BRACES {{...}} for template variables.
- Generate emails before sending (send_email requires approval)
- Create reminders for follow-ups
- Set approval_required to "required" for external actions (send_email)
- Set approval_required to "optional" for internal actions (create_task, create_reminder)

Return JSON with this structure:
{{
  "workflow_type": "...",
  "name": "...",
  "description": "...",
  "target_customers": {{...}},
  "steps": [
    {{
      "step_id": "step_1",
      "action": "customer_search",
      "description": "...",
      "parameters": {{...}},
      "depends_on": [],
      "approval_required": "none",
      "approval_description": ""
    }}
  ],
  "approval_required": "optional"
}}"""
        
        user_prompt = f"""User Request: {user_request}

Context: {json.dumps(context or {}, indent=2)}

Create a workflow plan."""
        
        try:
            response = client.chat.completions.create(
                model=settings.get_llm_config()["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=3000,
            )
            
            result_text = response.choices[0].message.content or "{}"
            plan_data = json.loads(result_text)
            
            # Validate and create plan
            plan = self._validate_and_create_plan(plan_data)
            logger.info(f"Created workflow plan: {plan.plan_id} ({plan.workflow_type.value})")
            return plan
            
        except Exception as e:
            logger.error(f"Workflow planning failed: {e}")
            raise
    
    def _validate_and_create_plan(self, data: dict) -> WorkflowPlan:
        """Validate and create WorkflowPlan from dictionary."""
        # Generate plan ID
        plan_id = data.get("plan_id", f"plan_{uuid.uuid4().hex[:12]}")
        
        # Validate workflow type
        try:
            workflow_type = WorkflowType(data["workflow_type"])
        except ValueError:
            workflow_type = WorkflowType.CUSTOM
        
        # Validate steps
        steps = []
        for i, step_data in enumerate(data.get("steps", [])):
            # Handle malformed step data
            if not isinstance(step_data, dict):
                logger.warning(f"Skipping malformed step data (not a dict): {step_data}")
                continue
            
            try:
                action = ActionType(step_data["action"])
            except ValueError:
                logger.warning(f"Unknown action: {step_data.get('action')}")
                continue
            except KeyError:
                logger.warning(f"Step missing action: {step_data}")
                continue
            
            step = WorkflowStep(
                step_id=step_data.get("step_id", f"step_{i+1}"),
                action=action,
                description=step_data.get("description", ""),
                parameters=step_data.get("parameters", {}),
                depends_on=step_data.get("depends_on", []),
                approval_required=ApprovalRequired(step_data.get("approval_required", "none")),
                approval_description=step_data.get("approval_description", ""),
            )
            steps.append(step)
        
        # Validate approval_required
        approval_required = ApprovalRequired(data.get("approval_required", "optional"))
        
        return WorkflowPlan(
            plan_id=plan_id,
            workflow_type=workflow_type,
            name=data.get("name", "Untitled Workflow"),
            description=data.get("description", ""),
            target_customers=data.get("target_customers", {}),
            steps=steps,
            approval_required=approval_required,
            created_at=datetime.now(),
            created_by="user",
            metadata=data.get("metadata", {}),
        )
    
    def execute_plan(
        self, 
        plan: WorkflowPlan, 
        auto_approve: bool = False,
        user_id: str = "system",
    ) -> list[ToolResult]:
        """Execute a workflow plan step by step with approval support.
        
        Args:
            plan: The workflow plan to execute
            auto_approve: If True, automatically approve all approval requests
            user_id: User ID for approval actions
        """
        context = WorkflowExecutionContext(plan=plan)
        context.variables["user"] = user_id
        results = []
        
        # Build dependency graph
        step_map = {step.step_id: step for step in plan.steps}
        executed = set()
        pending_approval_steps = {}  # step_id -> approval_id
        
        while len(executed) < len(plan.steps):
            progress = False
            for step in plan.steps:
                if step.step_id in executed:
                    continue
                
                # Check if this step is waiting for approval
                if step.step_id in pending_approval_steps:
                    approval_id = pending_approval_steps[step.step_id]
                    # Check approval status
                    from src.db import get_db
                    from src.services.approval import create_approval_service
                    db = next(get_db())
                    approval_service = create_approval_service(db)
                    approval = approval_service.get_approval(approval_id)
                    
                    if not approval:
                        result = ToolResult(success=False, error=f"Approval {approval_id} not found")
                    elif approval.status == ApprovalStatus.APPROVED:
                        # Approval granted, continue with step
                        result = self._execute_step(step, context, auto_approve, user_id)
                        del pending_approval_steps[step.step_id]
                    elif approval.status in [ApprovalStatus.REJECTED, ApprovalStatus.EDITED]:
                        # Approval denied or edited
                        result = ToolResult(
                            success=False, 
                            error=f"Approval {approval.status.value}: {approval.rejection_reason or 'Content edited'}"
                        )
                        del pending_approval_steps[step.step_id]
                    else:
                        # Still pending - skip for now
                        logger.info(f"Step {step.step_id} waiting for approval {approval_id}")
                        continue
                else:
                    # Execute step normally
                    result = self._execute_step(step, context, auto_approve, user_id)
                
                # Check if step requires approval
                if result.success and step.approval_required == ApprovalRequired.REQUIRED:
                    # Check if the result indicates an approval was requested
                    if result.data and result.data.get("status") == "pending":
                        approval_id = result.data.get("approval_id")
                        if approval_id:
                            pending_approval_steps[step.step_id] = approval_id
                            logger.info(f"Step {step.step_id} paused for approval {approval_id}")
                            # Don't mark as executed, will retry after approval
                            continue
                    elif auto_approve and result.data and result.data.get("status") == "auto_approved":
                        pass  # Already auto-approved
                
                context.step_results[step.step_id] = result
                results.append(result)
                executed.add(step.step_id)
                progress = True
                
                logger.info(f"Executed step {step.step_id} ({step.action.value}): {'success' if result.success else 'failed'}")
                
                if not result.success:
                    context.errors.append(f"Step {step.step_id} failed: {result.error}")
            
            # Check for progress
            if not progress:
                # Check if any steps are pending approval
                if pending_approval_steps:
                    logger.info(f"Workflow paused, waiting for {len(pending_approval_steps)} approvals")
                    # In a real system, this would return a "waiting" state
                    # For now, we'll break and return what we have
                    break
                else:
                    # Circular dependency or missing dependency
                    remaining = [s.step_id for s in plan.steps if s.step_id not in executed]
                    for step_id in remaining:
                        context.errors.append(f"Step {step_id} could not execute (dependency issue)")
                        executed.add(step_id)
                    break
        
        return results
    
    def _execute_step(self, step: "WorkflowStep", context: "WorkflowExecutionContext", auto_approve: bool, user_id: str) -> "ToolResult":
        """Execute a single step."""
        tool = self.registry.get(step.action.value)
        
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {step.action.value}",
            )
        
        # Inject context variables into parameters
        params = self._inject_context_variables(step.parameters, context)
        
        # Add auto_approve and user to context for tools that need it
        context.variables["auto_approve"] = auto_approve
        context.variables["user"] = user_id
        
        result = tool.execute(context, params)
        return result
    
    def _inject_context_variables(self, parameters: dict[str, Any], context: WorkflowExecutionContext) -> dict[str, Any]:
        """Inject context variables into step parameters."""
        # Simple implementation - replace {{variable}} or {variable} placeholders and auto-inject selected_customers for customer_ids
        import re
        import json
        
        # Track which fields were resolved from step results so we can convert JSON strings back to lists
        resolved_array_fields: set[str] = set()
        
        def replace_vars(obj):
            if isinstance(obj, str):
                def replacer(match):
                    # Group 1 is for {{...}}, group 2 for {...}
                    var_name = match.group(1) or match.group(2)
                    if var_name in context.variables:
                        return str(context.variables[var_name])
                    if var_name == "selected_customers":
                        return json.dumps(context.selected_customers)
                    # Handle step result references like {{step_1.result.customer_ids}} or {step_1.result.customer_ids}
                    if var_name.startswith("step_") and ".result." in var_name:
                        # Extract step_id and field
                        parts = var_name.split(".result.")
                        if len(parts) == 2:
                            step_id, field = parts
                            if step_id in context.step_results:
                                result = context.step_results[step_id]
                                if result.success and result.data and field in result.data:
                                    # Mark this field as resolved from a step result (likely an array)
                                    # We'll convert it back from JSON after substitution
                                    resolved_array_fields.add(f"parameters.{var_name}")
                                    return json.dumps(result.data[field])
                        return match.group(0)
                    return match.group(0)
                # Match both {{var}} and {var} patterns
                return re.sub(r'\{\{([\w.]+)\}\}|\{([\w.]+)\}', lambda m: replacer(m), obj)
            elif isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    # Auto-inject selected_customers as customer_ids if customer_ids is expected but not provided
                    if k == "customer_ids" and (v == [] or v is None or v == ""):
                        if context.selected_customers:
                            result[k] = [c["customer_id"] for c in context.selected_customers]
                        else:
                            result[k] = []
                    else:
                        result[k] = replace_vars(v)
                return result
            elif isinstance(obj, list):
                return [replace_vars(item) for item in obj]
            return obj
        
        # First pass: string substitution
        result = replace_vars(parameters)
        
        # First pass: string substitution
        result = replace_vars(parameters)
        
        # Second pass: Convert JSON array strings back to Python lists
        def convert_json_arrays(obj):
            if isinstance(obj, dict):
                new_dict = {}
                for k, v in obj.items():
                    if isinstance(v, str) and v.startswith('[') and v.endswith(']'):
                        try:
                            parsed = json.loads(v)
                            if isinstance(parsed, list):
                                new_dict[k] = parsed
                            else:
                                new_dict[k] = v
                        except json.JSONDecodeError:
                            new_dict[k] = v
                    else:
                        new_dict[k] = convert_json_arrays(v)
                return new_dict
            elif isinstance(obj, list):
                return [convert_json_arrays(item) for item in obj]
            return obj
        
        # First pass: string substitution
        result = replace_vars(parameters)
        # Second pass: convert JSON array strings back to Python lists
        return convert_json_arrays(result)


def create_workflow_planner() -> WorkflowPlanner:
    """Factory function to create workflow planner."""
    return WorkflowPlanner()