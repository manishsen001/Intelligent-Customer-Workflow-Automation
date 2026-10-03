"""Customer Intelligence module for AI-powered customer analysis, segmentation, and scoring."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from openai import OpenAI

from src.config.logging_config import logger
from src.config.settings import settings
from src.db.models import (
    Customer,
    CustomerSegment,
    CustomerStatus,
    PaymentStatus,
    SupportStatus,
)

# Default scoring thresholds (configurable via environment)
DEFAULT_THRESHOLDS = {
    "high_value_purchase_threshold": 10000.0,
    "high_value_order_threshold": 10,
    "inactive_days_threshold": 30,
    "at_risk_days_threshold": 60,
    "churn_risk_days_threshold": 90,
    "engagement_high_threshold": 0.7,
    "engagement_low_threshold": 0.3,
    "follow_up_priority_high": 0.7,
    "follow_up_priority_low": 0.3,
}


@dataclass
class CustomerScore:
    """Individual score component with explanation."""
    score: float
    factors: list[str]
    max_score: float = 1.0
    
    @property
    def normalized(self) -> float:
        """Return normalized score (0-1)."""
        if self.max_score == 0:
            return 0.0
        return min(max(self.score / self.max_score, 0.0), 1.0)


@dataclass
class CustomerAnalysis:
    """Complete AI analysis result for a customer."""
    customer_id: str
    summary: str
    segment: CustomerSegment
    segment_reasoning: str
    engagement_score: CustomerScore
    value_score: CustomerScore
    churn_risk: CustomerScore
    follow_up_priority: CustomerScore
    recommended_action: str
    recommended_communication_type: str
    priority: int
    confidence: float
    analyzed_at: datetime = field(default_factory=datetime.now)


class CustomerIntelligence:
    """Customer intelligence engine for segmentation, scoring, and AI analysis."""
    
    def __init__(self, thresholds: Optional[dict] = None):
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._llm_client: Optional[OpenAI] = None
    
    def _get_llm_client(self) -> OpenAI:
        """Get or create LLM client."""
        if self._llm_client is None:
            llm_config = settings.get_llm_config()
            self._llm_client = OpenAI(
                api_key=llm_config["api_key"],
                base_url=llm_config["base_url"],
            )
        return self._llm_client
    
    def calculate_engagement_score(self, customer: Customer) -> CustomerScore:
        """Calculate engagement score based on contact frequency and recency."""
        factors = []
        score = 0.0
        max_score = 10.0
        
        now = datetime.now()
        
        # Recency of last contact (0-4 points)
        if customer.last_contact_date:
            days_since_contact = (now - customer.last_contact_date).days
            if days_since_contact <= 7:
                score += 4
                factors.append(f"Recent contact ({days_since_contact} days ago)")
            elif days_since_contact <= 30:
                score += 2
                factors.append(f"Contact within 30 days ({days_since_contact} days ago)")
            elif days_since_contact <= 60:
                score += 1
                factors.append(f"Contact within 60 days ({days_since_contact} days ago)")
            else:
                factors.append(f"No contact for {days_since_contact} days")
        else:
            factors.append("No contact history")
        
        # Order frequency (0-3 points)
        if customer.order_count >= self.thresholds["high_value_order_threshold"]:
            score += 3
            factors.append(f"High order count ({customer.order_count})")
        elif customer.order_count >= 5:
            score += 2
            factors.append(f"Moderate order count ({customer.order_count})")
        elif customer.order_count >= 1:
            score += 1
            factors.append(f"Low order count ({customer.order_count})")
        else:
            factors.append("No orders")
        
        # Recent purchase (0-3 points)
        if customer.last_purchase_date:
            days_since_purchase = (now - customer.last_purchase_date).days
            if days_since_purchase <= 30:
                score += 3
                factors.append(f"Recent purchase ({days_since_purchase} days ago)")
            elif days_since_purchase <= 90:
                score += 2
                factors.append(f"Purchase within 90 days ({days_since_purchase} days ago)")
            else:
                score += 1
                factors.append(f"Old purchase ({days_since_purchase} days ago)")
        else:
            factors.append("No purchase history")
        
        return CustomerScore(score=score, factors=factors, max_score=max_score)
    
    def calculate_value_score(self, customer: Customer) -> CustomerScore:
        """Calculate customer value score based on purchase value and order count."""
        factors = []
        score = 0.0
        max_score = 10.0
        
        # Total purchase value (0-6 points)
        if customer.total_purchase_value >= self.thresholds["high_value_purchase_threshold"]:
            score += 6
            factors.append(f"High total value (${customer.total_purchase_value:,.2f})")
        elif customer.total_purchase_value >= 5000:
            score += 4
            factors.append(f"Good total value (${customer.total_purchase_value:,.2f})")
        elif customer.total_purchase_value >= 1000:
            score += 2
            factors.append(f"Moderate total value (${customer.total_purchase_value:,.2f})")
        elif customer.total_purchase_value > 0:
            score += 1
            factors.append(f"Low total value (${customer.total_purchase_value:,.2f})")
        else:
            factors.append("No purchase value")
        
        # Order count contribution (0-2 points)
        if customer.order_count >= 20:
            score += 2
            factors.append(f"Very frequent buyer ({customer.order_count} orders)")
        elif customer.order_count >= 10:
            score += 1.5
            factors.append(f"Frequent buyer ({customer.order_count} orders)")
        elif customer.order_count >= 5:
            score += 1
            factors.append(f"Regular buyer ({customer.order_count} orders)")
        elif customer.order_count > 0:
            score += 0.5
            factors.append(f"Occasional buyer ({customer.order_count} orders)")
        
        # Payment status (0-2 points)
        if customer.payment_status == PaymentStatus.CURRENT:
            score += 2
            factors.append("Current payment status")
        elif customer.payment_status == PaymentStatus.PARTIAL:
            score += 1
            factors.append("Partial payment")
        elif customer.payment_status == PaymentStatus.OVERDUE:
            factors.append("Overdue payment")
        elif customer.payment_status == PaymentStatus.DISPUTED:
            factors.append("Payment dispute")
        
        return CustomerScore(score=score, factors=factors, max_score=max_score)
    
    def calculate_churn_risk(self, customer: Customer) -> CustomerScore:
        """Calculate churn risk score (higher = more risk)."""
        factors = []
        score = 0.0
        max_score = 10.0
        
        now = datetime.now()
        
        # Days since last contact (0-5 points for risk)
        if customer.last_contact_date:
            days_since_contact = (now - customer.last_contact_date).days
            if days_since_contact >= self.thresholds["churn_risk_days_threshold"]:
                score += 5
                factors.append(f"No contact for {days_since_contact} days (churn risk)")
            elif days_since_contact >= self.thresholds["at_risk_days_threshold"]:
                score += 3
                factors.append(f"No contact for {days_since_contact} days (at risk)")
            elif days_since_contact >= self.thresholds["inactive_days_threshold"]:
                score += 1
                factors.append(f"No contact for {days_since_contact} days (inactive)")
        else:
            score += 5
            factors.append("Never contacted")
        
        # Payment issues (0-2 points)
        if customer.payment_status == PaymentStatus.OVERDUE:
            score += 2
            factors.append("Overdue payments")
        elif customer.payment_status == PaymentStatus.DISPUTED:
            score += 2
            factors.append("Payment dispute")
        elif customer.payment_status == PaymentStatus.PARTIAL:
            score += 1
            factors.append("Partial payments")
        
        # Support issues (0-2 points)
        if customer.support_status in [SupportStatus.OPEN, SupportStatus.IN_PROGRESS, SupportStatus.ESCALATED]:
            score += 2
            factors.append(f"Active support issue ({customer.support_status.value})")
        elif customer.support_status == SupportStatus.RESOLVED:
            score += 0.5
            factors.append("Recently resolved support issue")
        
        # Outstanding amount (0-1 point)
        if customer.outstanding_amount > 0:
            score += 1
            factors.append(f"Outstanding amount: ${customer.outstanding_amount:,.2f}")
        
        return CustomerScore(score=score, factors=factors, max_score=max_score)
    
    def calculate_follow_up_priority(self, customer: Customer) -> CustomerScore:
        """Calculate follow-up priority based on all factors."""
        factors = []
        score = 0.0
        max_score = 10.0
        
        # High value customer needs attention
        value_score = self.calculate_value_score(customer)
        if value_score.normalized >= 0.7:
            score += 2
            factors.append("High-value customer")
        elif value_score.normalized >= 0.4:
            score += 1
            factors.append("Medium-value customer")
        
        # Churn risk needs follow-up
        churn_score = self.calculate_churn_risk(customer)
        if churn_score.normalized >= 0.5:
            score += 3
            factors.append("Elevated churn risk")
        
        # Engagement opportunity
        engagement_score = self.calculate_engagement_score(customer)
        if engagement_score.normalized <= 0.3 and value_score.normalized >= 0.3:
            score += 2
            factors.append("Low engagement but has value")
        
        # Overdue payment
        if customer.payment_status == PaymentStatus.OVERDUE:
            score += 2
            factors.append("Overdue payment - needs collection follow-up")
        
        # Active support issue
        if customer.support_status in [SupportStatus.OPEN, SupportStatus.IN_PROGRESS]:
            score += 1
            factors.append("Active support issue")
        
        return CustomerScore(score=score, factors=factors, max_score=max_score)
    
    def determine_segment(
        self,
        customer: Customer,
        engagement_score: CustomerScore,
        value_score: CustomerScore,
        churn_score: CustomerScore,
        follow_up_score: CustomerScore,
    ) -> tuple[CustomerSegment, str]:
        """Determine customer segment based on scores."""
        reasoning_parts = []
        
        # High value customer
        if value_score.normalized >= 0.7 and customer.total_purchase_value >= self.thresholds["high_value_purchase_threshold"]:
            return CustomerSegment.HIGH_VALUE_CUSTOMER, "High total purchase value and frequent orders"
        
        # Payment risk
        if customer.payment_status == PaymentStatus.OVERDUE or customer.outstanding_amount > 1000:
            return CustomerSegment.PAYMENT_RISK, "Overdue payments or significant outstanding amount"
        
        # At risk
        if churn_score.normalized >= 0.5:
            return CustomerSegment.AT_RISK_CUSTOMER, f"Elevated churn risk (score: {churn_score.normalized:.0%})"
        
        # Inactive
        if customer.last_contact_date:
            days_since = (datetime.now() - customer.last_contact_date).days
            if days_since >= self.thresholds["inactive_days_threshold"] and customer.customer_status != CustomerStatus.CHURNED:
                return CustomerSegment.INACTIVE_CUSTOMER, f"No contact for {days_since} days"
        
        # Loyal customer
        if value_score.normalized >= 0.5 and engagement_score.normalized >= 0.5:
            return CustomerSegment.LOYAL_CUSTOMER, "Good value and engagement"
        
        # Active customer
        if engagement_score.normalized >= 0.4:
            return CustomerSegment.ACTIVE_CUSTOMER, "Regular engagement"
        
        # New customer
        if customer.order_count <= 1 and customer.total_purchase_value < 1000:
            return CustomerSegment.NEW_CUSTOMER, "New or potential customer"
        
        # Potential lead
        return CustomerSegment.POTENTIAL_LEAD, "Potential lead with limited history"
    
    def analyze_customer_with_ai(self, customer: Customer) -> Optional[CustomerAnalysis]:
        """Use AI to analyze customer and generate insights."""
        try:
            client = self._get_llm_client()
            
            # Prepare customer context
            context = {
                "customer_id": customer.customer_id,
                "name": customer.name,
                "email": customer.email,
                "company": customer.company,
                "customer_type": customer.customer_type.value,
                "total_purchase_value": customer.total_purchase_value,
                "order_count": customer.order_count,
                "payment_status": customer.payment_status.value,
                "outstanding_amount": customer.outstanding_amount,
                "support_status": customer.support_status.value,
                "customer_status": customer.customer_status.value,
                "last_contact_date": customer.last_contact_date.isoformat() if customer.last_contact_date else None,
                "last_purchase_date": customer.last_purchase_date.isoformat() if customer.last_purchase_date else None,
            }
            
            system_prompt = """You are a Customer Intelligence Analyst. Analyze the customer data and provide:
1. A concise summary (2-3 sentences)
2. Recommended segment (new_customer, active_customer, loyal_customer, at_risk_customer, inactive_customer, high_value_customer, potential_lead, payment_risk)
3. Segment reasoning with specific data points
4. Recommended next action
5. Recommended communication type (email, call, meeting, automated)
6. Priority (1-100)
7. Confidence (0-1)

Respond with valid JSON only."""
            
            user_prompt = f"""Customer Data:
{json.dumps(context, indent=2)}"""
            
            response = client.chat.completions.create(
                model=settings.get_llm_config()["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=1000,
            )
            
            result_text = response.choices[0].message.content or "{}"
            ai_result = json.loads(result_text)
            
            # Calculate local scores for validation
            engagement = self.calculate_engagement_score(customer)
            value = self.calculate_value_score(customer)
            churn = self.calculate_churn_risk(customer)
            follow_up = self.calculate_follow_up_priority(customer)
            
            # Determine segment using local logic as fallback
            segment_str = ai_result.get("segment", "potential_lead")
            try:
                segment = CustomerSegment(segment_str)
            except ValueError:
                segment, _ = self.determine_segment(customer, engagement, value, churn, follow_up)
            
            return CustomerAnalysis(
                customer_id=customer.customer_id,
                summary=ai_result.get("summary", "AI analysis completed"),
                segment=segment,
                segment_reasoning=ai_result.get("segment_reasoning", ""),
                engagement_score=engagement,
                value_score=value,
                churn_risk=churn,
                follow_up_priority=follow_up,
                recommended_action=ai_result.get("recommended_action", "Review customer profile"),
                recommended_communication_type=ai_result.get("recommended_communication_type", "email"),
                priority=ai_result.get("priority", 50),
                confidence=ai_result.get("confidence", 0.7),
            )
            
        except Exception as e:
            logger.error(f"AI analysis failed for customer {customer.customer_id}: {e}")
            return None
    
    def analyze_customer(self, customer: Customer, use_ai: bool = True) -> CustomerAnalysis:
        """Analyze a customer and return complete analysis."""
        # Calculate local scores
        engagement = self.calculate_engagement_score(customer)
        value = self.calculate_value_score(customer)
        churn = self.calculate_churn_risk(customer)
        follow_up = self.calculate_follow_up_priority(customer)
        
        # Determine segment
        segment, segment_reasoning = self.determine_segment(customer, engagement, value, churn, follow_up)
        
        # Try AI analysis
        ai_analysis = None
        if use_ai and settings.get_llm_config().get("api_key"):
            ai_analysis = self.analyze_customer_with_ai(customer)
        
        if ai_analysis:
            # Merge AI insights with local scores
            ai_analysis.engagement_score = engagement
            ai_analysis.value_score = value
            ai_analysis.churn_risk = churn
            ai_analysis.follow_up_priority = follow_up
            return ai_analysis
        
        # Fallback to rule-based analysis
        return CustomerAnalysis(
            customer_id=customer.customer_id,
            summary=f"Customer with {customer.order_count} orders totaling ${customer.total_purchase_value:,.2f}. "
                    f"Last contact: {customer.last_contact_date.strftime('%Y-%m-%d') if customer.last_contact_date else 'Never'}. "
                    f"Payment status: {customer.payment_status.value}.",
            segment=segment,
            segment_reasoning=segment_reasoning,
            engagement_score=engagement,
            value_score=value,
            churn_risk=churn,
            follow_up_priority=follow_up,
            recommended_action=self._get_default_recommendation(customer, segment),
            recommended_communication_type="email",
            priority=min(100, int(follow_up.normalized * 100)),
            confidence=0.7,
        )
    
    def _get_default_recommendation(self, customer: Customer, segment: CustomerSegment) -> str:
        """Get default recommendation based on segment."""
        recommendations = {
            CustomerSegment.HIGH_VALUE_CUSTOMER: "Schedule executive check-in and offer premium services",
            CustomerSegment.PAYMENT_RISK: "Send payment reminder and offer payment plan options",
            CustomerSegment.AT_RISK_CUSTOMER: "Initiate re-engagement campaign with personalized offer",
            CustomerSegment.INACTIVE_CUSTOMER: "Send re-engagement email with special incentive",
            CustomerSegment.LOYAL_CUSTOMER: "Thank them and introduce loyalty rewards",
            CustomerSegment.ACTIVE_CUSTOMER: "Continue regular engagement and cross-sell",
            CustomerSegment.NEW_CUSTOMER: "Send welcome sequence and onboarding materials",
            CustomerSegment.POTENTIAL_LEAD: "Qualify lead and schedule discovery call",
        }
        return recommendations.get(segment, "Review customer profile and determine next steps")
    
    def batch_analyze(self, customers: list[Customer], use_ai: bool = True) -> list[CustomerAnalysis]:
        """Analyze multiple customers."""
        results = []
        for customer in customers:
            analysis = self.analyze_customer(customer, use_ai=use_ai)
            results.append(analysis)
        return results
    
    def update_customer_scores(self, customer: Customer, analysis: CustomerAnalysis) -> None:
        """Update customer record with analysis results."""
        customer.engagement_score = analysis.engagement_score.normalized
        customer.value_score = analysis.value_score.normalized
        customer.churn_risk = analysis.churn_risk.normalized
        customer.follow_up_priority = analysis.follow_up_priority.normalized
        customer.customer_segment = analysis.segment
        customer.segment_reasoning = analysis.segment_reasoning
        customer.ai_summary = analysis.summary
        customer.ai_recommendations = {
            "recommended_action": analysis.recommended_action,
            "recommended_communication_type": analysis.recommended_communication_type,
            "priority": analysis.priority,
        }
        customer.priority = analysis.priority
        customer.updated_at = datetime.now()


def create_customer_intelligence(thresholds: Optional[dict] = None) -> CustomerIntelligence:
    """Factory function to create customer intelligence engine."""
    return CustomerIntelligence(thresholds)