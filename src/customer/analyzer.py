"""Customer analyzer for intelligent customer analysis and insights."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, List

from openai import OpenAI

from src.config.logging_config import logger
from src.config.settings import settings
from src.services.customer_intelligence import (
    CustomerIntelligence,
    CustomerAnalysis,
    CustomerScore,
    create_customer_intelligence,
)
from src.db.models import (
    Customer,
    CustomerSegment,
    CustomerStatus,
    PaymentStatus,
    SupportStatus,
)
from src.db.repositories import CustomerRepository
from src.db.service import get_db
from src.customer.models import (
    CustomerInsight,
    CustomerPriority,
    CustomerSegment,
    CustomerFollowUpStatus,
    CUSTOMER_SEGMENTS,
)


class CustomerAnalyzer:
    """Advanced customer analyzer for intelligent insights and recommendations."""
    
    def __init__(self, thresholds: Optional[dict] = None):
        self.intelligence = create_customer_intelligence()
        self.thresholds = {**{
            "high_value_purchase_threshold": 10000.0,
            "high_value_order_threshold": 10,
            "inactive_days_threshold": 30,
            "at_risk_days_threshold": 60,
            "churn_risk_days_threshold": 90,
        }, **(thresholds or {})}
    
    def get_customers_requiring_follow_up(self, days_threshold: int = 30) -> list[dict]:
        """Get customers who haven't been contacted in the specified days."""
        db = next(get_db())
        repo = CustomerRepository(db)
        
        try:
            # Get customers with last contact older than threshold
            cutoff_date = datetime.now() - timedelta(days=days_threshold)
            
            filters = {
                "last_contact_before": cutoff_date,
                "customer_status": ["active", "prospect"]
            }
            
            customers = repo.list_customers(filters=filters, limit=1000)
            
            results = []
            for customer in customers:
                days_since = (datetime.now() - customer.last_contact_date).days if customer.last_contact_date else 999
                if days_since >= days_threshold:
                    results.append({
                        "customer_id": customer.customer_id,
                        "name": customer.name,
                        "email": customer.email,
                        "days_since_contact": days_since,
                        "last_contact_date": customer.last_contact_date.isoformat() if customer.last_contact_date else None,
                        "customer_segment": customer.customer_segment.value if customer.customer_segment else None,
                        "priority_score": customer.follow_up_priority or 0,
                    })
            
            return sorted(results, key=lambda x: x.get("priority_score", 0), reverse=True)
        finally:
            db.close()
    
    def get_high_value_customers(self, min_value: float = 10000.0, min_orders: int = 10) -> list[dict]:
        """Get high-value customers based on purchase value and order count."""
        db = next(get_db())
        repo = CustomerRepository(db)
        
        try:
            filters = {
                "min_purchase_value": min_value,
                "min_order_count": min_orders,
            }
            customers = repo.list_customers(filters=filters, limit=500)
            
            results = []
            for customer in customers:
                results.append({
                    "customer_id": customer.customer_id,
                    "name": customer.name,
                    "email": customer.email,
                    "total_purchase_value": customer.total_purchase_value,
                    "order_count": customer.order_count,
                    "customer_segment": customer.customer_segment.value if customer.customer_segment else None,
                })
            
            return sorted(results, key=lambda x: x["total_purchase_value"], reverse=True)
        finally:
            db.close()
    
    def get_at_risk_customers(self) -> list[dict]:
        """Get customers at risk of churning."""
        db = next(get_db())
        repo = CustomerRepository(db)
        
        try:
            # Get customers with high churn risk
            all_customers = repo.list_customers(limit=1000)
            
            results = []
            for customer in all_customers:
                # Calculate churn risk using the intelligence engine
                analysis = self.analyze_customer(customer)
                if analysis and analysis.churn_risk.normalized >= 0.5:
                    results.append({
                        "customer_id": customer.customer_id,
                        "name": customer.name,
                        "email": customer.email,
                        "churn_risk": analysis.churn_risk.normalized,
                        "churn_factors": analysis.churn_risk.factors,
                        "last_contact_date": customer.last_contact_date.isoformat() if customer.last_contact_date else None,
                        "days_since_contact": (datetime.now() - customer.last_contact_date).days if customer.last_contact_date else 999,
                    })
            
            return sorted(results, key=lambda x: x["churn_risk"], reverse=True)
        finally:
            db.close()
    
    def get_inactive_customers(self, days: int = 30) -> list[dict]:
        """Get customers with no contact for specified days."""
        return self.get_customers_requiring_follow_up(days)
    
    def get_payment_risk_customers(self) -> list[dict]:
        """Get customers with payment issues."""
        db = next(get_db())
        repo = CustomerRepository(db)
        
        try:
            filters = {
                "payment_status": "overdue",
                "outstanding_amount_gt": 0
            }
            customers = repo.list_customers(filters=filters, limit=500)
            
            results = []
            for customer in customers:
                results.append({
                    "customer_id": customer.customer_id,
                    "name": customer.name,
                    "email": customer.email,
                    "outstanding_amount": customer.outstanding_amount,
                    "payment_status": customer.payment_status.value,
                    "days_overdue": (datetime.now() - customer.last_purchase_date).days if customer.last_purchase_date else 0,
                })
            
            return sorted(results, key=lambda x: x["outstanding_amount"], reverse=True)
        finally:
            db.close()
    
    def get_new_customers(self, days: int = 30) -> list[dict]:
        """Get customers who signed up recently."""
        db = next(get_db())
        repo = CustomerRepository(db)
        
        try:
            cutoff = datetime.now() - timedelta(days=days)
            filters = {"signup_after": cutoff}
            customers = repo.list_customers(filters=filters, limit=500)
            
            results = []
            for customer in customers:
                results.append({
                    "customer_id": customer.customer_id,
                    "name": customer.name,
                    "email": customer.email,
                    "signup_date": customer.signup_date.isoformat() if customer.signup_date else None,
                    "order_count": customer.order_count,
                    "total_purchase_value": customer.total_purchase_value,
                })
            
            return results
        finally:
            db.close()
    
    def analyze_customer_segment(self, customer: Customer) -> dict:
        """Get detailed segment analysis for a customer."""
        analysis = self.intelligence.analyze_customer(customer)
        
        return {
            "customer_id": customer.customer_id,
            "segment": analysis.segment.value,
            "segment_reasoning": analysis.segment_reasoning,
            "engagement_score": analysis.engagement_score.normalized,
            "value_score": analysis.value_score.normalized,
            "churn_risk": analysis.churn_risk.normalized,
            "follow_up_priority": analysis.follow_up_priority.normalized,
            "recommended_action": analysis.recommended_action,
            "recommended_communication": analysis.recommended_communication_type,
            "priority": analysis.priority,
            "confidence": analysis.confidence,
        }
    
    def generate_insights(self, customer: Customer) -> list[CustomerInsight]:
        """Generate actionable insights for a customer."""
        insights = []
        analysis = self.analyze_customer_segment(customer)
        
        # Churn risk insight
        if analysis["churn_risk"] > 0.5:
            insights.append(CustomerInsight(
                customer_id=customer.customer_id,
                insight_type="warning",
                title="High Churn Risk",
                description=f"Customer has {analysis['churn_risk']:.0%} churn risk. Last contact was {(datetime.now() - customer.last_contact_date).days if customer.last_contact_date else 'never'} days ago.",
                confidence=analysis["confidence"],
                priority=CustomerPriority.HIGH,
                suggested_actions=[
                    "Send re-engagement email with special offer",
                    "Schedule check-in call",
                    "Review support tickets for unresolved issues"
                ],
            ))
        
        # Payment risk insight
        if customer.payment_status.value == "overdue" or customer.outstanding_amount > 1000:
            insights.append(CustomerInsight(
                customer_id=customer.customer_id,
                insight_type="warning",
                title="Payment Risk",
                description=f"Customer has ${customer.outstanding_amount:,.2f} outstanding with {customer.payment_status.value} status.",
                confidence=0.9,
                priority=CustomerPriority.HIGH,
                suggested_actions=[
                    "Send payment reminder email",
                    "Offer payment plan options",
                    "Escalate to collections if needed"
                ],
            ))
        
        # High value customer insight
        if analysis["value_score"] >= 0.7:
            insights.append(CustomerInsight(
                customer_id=customer.customer_id,
                insight_type="opportunity",
                title="High-Value Customer",
                description=f"Customer has ${customer.total_purchase_value:,.2f} in total purchases across {customer.order_count} orders.",
                confidence=analysis["confidence"],
                priority=CustomerPriority.MEDIUM,
                suggested_actions=[
                    "Schedule executive check-in",
                    "Offer premium services/early access",
                    "Enroll in VIP program"
                ],
            ))
        
        # Inactive customer insight
        if customer.last_contact_date:
            days_since = (datetime.now() - customer.last_contact_date).days
            if days_since >= 30:
                insights.append(CustomerInsight(
                    customer_id=customer.customer_id,
                    insight_type="warning",
                    title="Inactive Customer",
                    description=f"No contact for {days_since} days. Last contact: {customer.last_contact_date.strftime('%Y-%m-%d')}.",
                    confidence=0.8,
                    priority=CustomerPriority.MEDIUM,
                    suggested_actions=[
                        "Send re-engagement email",
                        "Offer special incentive to return",
                        "Schedule check-in call"
                    ],
                ))
        
        # New customer insight
        if customer.order_count <= 1 and customer.total_purchase_value < 1000:
            insights.append(CustomerInsight(
                customer_id=customer.customer_id,
                insight_type="opportunity",
                title="New Customer Onboarding",
                description=f"New customer with {customer.order_count} order(s) and ${customer.total_purchase_value:,.2f} total value.",
                confidence=0.8,
                priority=CustomerPriority.MEDIUM,
                suggested_actions=[
                    "Send welcome email sequence",
                    "Provide onboarding materials",
                    "Schedule welcome call"
                ],
            ))
        
        return insights
    
    def get_recommended_actions(self, customer: Customer) -> list[dict]:
        """Get recommended actions for a customer based on their profile."""
        actions = []
        analysis = self.analyze_customer_segment(customer)
        
        # Follow-up actions based on segment
        segment = analysis["segment"]
        
        if segment == "at_risk_customer":
            actions.append({
                "action": "send_reengagement_email",
                "priority": "high",
                "description": "Send personalized re-engagement email with special offer",
                "template": "re_engagement",
            })
            actions.append({
                "action": "schedule_call",
                "priority": "high",
                "description": "Schedule check-in call to address concerns",
            })
        
        elif segment == "inactive_customer":
            actions.append({
                "action": "send_reengagement_email",
                "priority": "high",
                "description": "Send re-engagement email with incentive",
                "template": "re_engagement",
            })
        
        elif segment == "payment_risk":
            actions.append({
                "action": "send_payment_reminder",
                "priority": "high",
                "description": "Send payment reminder with payment options",
                "template": "payment_reminder",
            })
        
        elif segment == "high_value_customer":
            actions.append({
                "action": "schedule_checkin",
                "priority": "medium",
                "description": "Schedule executive check-in call",
            })
            actions.append({
                "action": "offer_premium",
                "priority": "medium",
                "description": "Offer premium services or early access",
            })
        
        elif segment == "new_customer":
            actions.append({
                "action": "send_welcome",
                "priority": "high",
                "description": "Send welcome email sequence",
                "template": "welcome",
            })
            actions.append({
                "action": "schedule_onboarding",
                "priority": "medium",
                "description": "Schedule onboarding call",
            })
        
        elif segment == "potential_lead":
            actions.append({
                "action": "qualify_lead",
                "priority": "medium",
                "description": "Schedule discovery call to qualify lead",
            })
        
        elif segment == "active_customer" or segment == "loyal_customer":
            actions.append({
                "action": "cross_sell",
                "priority": "medium",
                "description": "Recommend complementary products/services",
            })
        
        return actions
    
    def batch_analyze(self, customers: list[Customer], use_ai: bool = True) -> list[dict]:
        """Analyze multiple customers and return insights for each."""
        results = []
        for customer in customers:
            analysis = self.analyze_customer_segment(customer)
            insights = self.generate_insights(customer)
            actions = self.get_recommended_actions(customer)
            
            results.append({
                "customer_id": customer.customer_id,
                "name": customer.name,
                "email": customer.email,
                "analysis": analysis,
                "insights": [
                    {
                        "type": i.insight_type,
                        "title": i.title,
                        "description": i.description,
                        "priority": i.priority.name,
                        "actions": i.suggested_actions,
                    } for i in insights
                ],
                "recommended_actions": actions,
            })
        return results


def create_customer_analyzer(thresholds: Optional[dict] = None) -> CustomerAnalyzer:
    """Factory function to create customer analyzer."""
    return CustomerAnalyzer(thresholds)