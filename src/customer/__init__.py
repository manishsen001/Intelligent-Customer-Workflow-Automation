"""Customer module for Intelligent Customer Workflow Automation System."""

from src.customer.models import (
    CustomerAction,
    CustomerActionType,
    CustomerFollowUp,
    CustomerFollowUpStatus,
    CustomerPriority,
)

from src.customer.analyzer import CustomerAnalyzer, create_customer_analyzer
from src.customer.service import CustomerService, create_customer_service

__all__ = [
    "CustomerAction",
    "CustomerActionType",
    "CustomerFollowUp",
    "CustomerFollowUpStatus",
    "CustomerPriority",
    "CustomerAnalyzer",
    "create_customer_analyzer",
    "CustomerService",
    "create_customer_service",
]