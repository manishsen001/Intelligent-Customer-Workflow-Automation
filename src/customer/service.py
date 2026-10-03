"""Customer service for managing customer workflows and actions."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, List

from src.config.logging_config import logger
from src.config.settings import settings
from src.db import get_db
from src.db.models import (
    Customer,
    Task,
    TaskStatus,
    FollowUp,
    FollowUpStatus,
    Reminder,
)
from src.workflows.reminder import ReminderFrequency
from src.db.repositories import (
    CustomerRepository,
    TaskRepository,
    FollowUpRepository,
    ReminderRepository,
)
from src.services.customer_intelligence import create_customer_intelligence
from src.services.customer_email import (
    create_customer_email_service,
    EmailTemplateType,
)
from src.services.approval import create_approval_service
from src.customer.models import (
    CustomerAction,
    CustomerActionType,
    CustomerFollowUp,
    CustomerFollowUpStatus,
    CustomerPriority,
    CustomerSegment,
    CustomerInsight,
    CUSTOMER_SEGMENTS,
)


class CustomerService:
    """Service for managing customer workflows and actions."""
    
    def __init__(self, session: Optional[Any] = None):
        self.session = session
    
    def _get_session(self):
        """Get database session."""
        if self.session:
            return self.session
        return next(get_db())
    
    def _close_session(self, session):
        """Close session if we own it."""
        if session and not self.session:
            session.close()
    
    # Customer Follow-up Operations
    
    def create_follow_up(
        self,
        customer_id: str,
        title: str,
        reason: str,
        due_date: datetime,
        priority: int = 50,
        assigned_to: Optional[str] = None,
        next_action: Optional[str] = None,
        last_contact_date: Optional[datetime] = None,
    ) -> dict:
        """Create a new customer follow-up."""
        db = next(get_db())
        repo = FollowUpRepository(db)
        
        try:
            # Validate customer exists
            customer_repo = CustomerRepository(db)
            customer = customer_repo.get_by_customer_id(customer_id)
            if not customer:
                raise ValueError(f"Customer {customer_id} not found")
            
            # Generate title if not provided
            if not title:
                title = f"Follow up with {customer.name}"
            
            follow_up = FollowUp(
                customer_id=customer.id,
                title=title,
                reason=reason,
                status=FollowUpStatus.PENDING,
                priority=priority,
                due_date=due_date,
                assigned_task_id=None,
                last_contact_date=last_contact_date,
                next_action=next_action,
            )
            
            created = repo.create(follow_up)
            db.commit()
            
            return {
                "success": True,
                "follow_up_id": created.id,
                "message": f"Follow-up created for {customer.name}",
            }
        except Exception as e:
            logger.error(f"Error creating follow-up: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    def get_follow_up(self, follow_up_id: int) -> Optional[FollowUp]:
        """Get follow-up by ID."""
        db = next(get_db())
        repo = FollowUpRepository(db)
        try:
            return repo.get_by_id(follow_up_id)
        finally:
            db.close()
    
    def list_follow_ups(
        self,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[FollowUp]:
        """List follow-ups with optional filters."""
        db = next(get_db())
        repo = FollowUpRepository(db)
        try:
            status_enum = None
            if status:
                try:
                    status_enum = FollowUpStatus(status)
                except ValueError:
                    raise ValueError(f"Invalid status: {status}")
            
            return repo.list_follow_ups(
                customer_id=customer_id,
                status=status_enum,
                limit=limit,
            )
        finally:
            db.close()
    
    def update_follow_up_status(
        self,
        follow_up_id: int,
        status: str,
    ) -> dict:
        """Update follow-up status with validation."""
        db = next(get_db())
        repo = FollowUpRepository(db)
        
        try:
            new_status = FollowUpStatus(status)
            follow_up = repo.get_by_id(follow_up_id)
            if not follow_up:
                return {"success": False, "error": f"Follow-up {follow_up_id} not found"}
            
            # Validate transition
            if not self._is_valid_transition(follow_up.status, new_status):
                return {
                    "success": False,
                    "error": f"Invalid status transition from {follow_up.status.value} to {status}"
                }
            
            follow_up.status = new_status
            if new_status == FollowUpStatus.COMPLETED:
                follow_up.completed_at = datetime.now()
            
            repo.update(follow_up)
            db.commit()
            
            return {"success": True, "message": f"Status updated to {status}"}
        except ValueError:
            return {"success": False, "error": f"Invalid status: {status}"}
        except Exception as e:
            logger.error(f"Error updating follow-up status: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    def _is_valid_transition(self, current: FollowUpStatus, new: FollowUpStatus) -> bool:
        """Validate status transitions."""
        valid_transitions = {
            FollowUpStatus.PENDING: [FollowUpStatus.IN_PROGRESS, FollowUpStatus.WAITING_APPROVAL, FollowUpStatus.CANCELLED],
            FollowUpStatus.IN_PROGRESS: [FollowUpStatus.COMPLETED, FollowUpStatus.WAITING_APPROVAL, FollowUpStatus.CANCELLED],
            FollowUpStatus.WAITING_APPROVAL: [FollowUpStatus.IN_PROGRESS, FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED],
            FollowUpStatus.OVERDUE: [FollowUpStatus.IN_PROGRESS, FollowUpStatus.WAITING_APPROVAL, FollowUpStatus.CANCELLED],
            FollowUpStatus.COMPLETED: [],
            FollowUpStatus.CANCELLED: [],
        }
        return new in valid_transitions.get(current, [])
    
    def mark_overdue(self, follow_up_id: int) -> dict:
        """Mark a follow-up as overdue."""
        return self.update_follow_up_status(follow_up_id, FollowUpStatus.OVERDUE.value)
    
    def get_overdue_follow_ups(self) -> list:
        """Get all overdue follow-ups."""
        db = next(get_db())
        repo = FollowUpRepository(db)
        try:
            return repo.get_overdue_follow_ups()
        finally:
            db.close()
    
    def get_upcoming_follow_ups(self, days: int = 7) -> list:
        """Get upcoming follow-ups within specified days."""
        db = next(get_db())
        repo = FollowUpRepository(db)
        try:
            return repo.get_upcoming_follow_ups(days=days)
        finally:
            db.close()
    
    def get_high_priority_follow_ups(self, min_priority: int = 50) -> list:
        """Get high-priority follow-ups."""
        db = next(get_db())
        repo = FollowUpRepository(db)
        try:
            return repo.get_high_priority_follow_ups(min_priority=min_priority)
        finally:
            db.close()
    
    # Customer Task Operations
    
    def create_customer_task(
        self,
        customer_id: int,
        title: str,
        description: str = "",
        task_type: str = "follow_up",
        due_date: Optional[datetime] = None,
        priority: int = 10,
        assigned_to: Optional[str] = None,
    ) -> dict:
        """Create a task for a customer."""
        db = next(get_db())
        repo = TaskRepository(db)
        
        try:
            customer_repo = CustomerRepository(db)
            customer = customer_repo.get_by_id(customer_id)
            if not customer:
                return {"success": False, "error": f"Customer {customer_id} not found"}
            
            task = Task(
                customer_id=customer.id,
                title=title,
                description=description,
                task_type=task_type,
                status=TaskStatus.PENDING,
                priority=priority,
                due_date=due_date,
                assigned_to=assigned_to,
            )
            
            created = repo.create(task)
            db.commit()
            
            return {
                "success": True,
                "task_id": created.id,
                "message": f"Task created for customer {customer.name}",
            }
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    # Customer Analysis Operations
    
    def analyze_customer(self, customer_id: int, use_ai: bool = True) -> Optional[dict]:
        """Analyze a customer and return insights."""
        db = next(get_db())
        try:
            repo = CustomerRepository(db)
            customer = repo.get_by_id(customer_id)
            if not customer:
                return None
            
            intelligence = create_customer_intelligence()
            analysis = intelligence.analyze_customer(customer, use_ai=use_ai)
            
            if analysis:
                return {
                    "customer_id": analysis.customer_id,
                    "summary": analysis.summary,
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
            return None
        finally:
            db.close()
    
    def batch_analyze_customers(
        self,
        customer_ids: List[int],
        use_ai: bool = True,
    ) -> List[dict]:
        """Analyze multiple customers."""
        db = next(get_db())
        try:
            repo = CustomerRepository(db)
            intelligence = create_customer_intelligence()
            
            customers = []
            for cid in customer_ids:
                customer = repo.get_by_id(cid)
                if customer:
                    customers.append(customer)
            
            if not customers:
                return []
            
            analyses = intelligence.batch_analyze(customers, use_ai=use_ai)
            
            results = []
            for customer, analysis in zip(customers, analyses):
                results.append({
                    "customer_id": customer.customer_id,
                    "name": customer.name,
                    "email": customer.email,
                    "segment": analysis.segment.value,
                    "engagement_score": analysis.engagement_score.normalized,
                    "value_score": analysis.value_score.normalized,
                    "churn_risk": analysis.churn_risk.normalized,
                    "follow_up_priority": analysis.follow_up_priority.normalized,
                    "recommended_action": analysis.recommended_action,
                })
            
            return results
        finally:
            db.close()
    
    # Email Operations
    
    def generate_personalized_email(
        self,
        customer_id: int,
        template_type: str = "follow_up",
        tone: str = "professional",
        custom_purpose: Optional[str] = None,
    ) -> dict:
        """Generate a personalized email for a customer."""
        db = next(get_db())
        try:
            repo = CustomerRepository(db)
            customer = repo.get_by_id(customer_id)
            if not customer:
                return {"success": False, "error": "Customer not found"}
            
            if not customer.email:
                return {"success": False, "error": "Customer has no email address"}
            
            email_service = create_customer_email_service()
            
            template_map = {
                "follow_up": "follow_up",
                "re_engagement": "re_engagement",
                "payment_reminder": "payment_reminder",
                "welcome": "welcome",
                "support_followup": "support_followup",
                "high_value_checkin": "high_value_checkin",
            }
            
            from src.services.customer_email import EmailTemplateType
            template_type = EmailTemplateType(weblink_map.get(template_type, "custom"))
            
            draft = email_service.generate_email(
                customer=customer,
                template_type=template_type,
                tone="professional",
            )
            
            return {
                "success": True,
                "draft": {
                    "subject": draft.subject,
                    "body": draft.body,
                    "html_body": draft.html_body,
                    "template_type": draft.template_type.value,
                }
            }
        finally:
            db.close()
    
    def send_customer_email(
        self,
        customer_id: int,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        auto_approve: bool = False,
    ) -> dict:
        """Send an email to a customer with approval workflow."""
        db = next(get_db())
        try:
            email_service = create_customer_email_service()
            
            repo = CustomerRepository(db)
            customer = repo.get_by_id(customer_id)
            if not customer:
                return {"success": False, "error": "Customer not found"}
            
            from src.services.customer_email import EmailDraft, EmailTemplateType
            
            draft = EmailDraft(
                customer_id=customer.id,
                customer_email=customer.email,
                customer_name=customer.name,
                subject=subject,
                body=body,
                html_body=html_body,
                template_type=EmailTemplateType.CUSTOM,
            )
            
            result = email_service.send_email_with_approval(draft, auto_approve=auto_approve)
            return {
                "success": result.success,
                "message": result.message,
                "error": result.error,
            }
        finally:
            db.close()
    
    # Customer Segmentation
    
    def segment_customers(
        self,
        filters: Optional[dict] = None,
        limit: int = 1000,
    ) -> dict:
        """Segment customers based on filters or auto-segmentation."""
        db = next(get_db())
        try:
            repo = CustomerRepository(db)
            intelligence = create_customer_intelligence()
            
            customers = repo.list_customers(limit=limit, filters=filters)
            
            if not customers:
                return {"segments": {}, "total": 0}
            
            # Analyze all customers
            analyses = intelligence.batch_analyze(customers, use_ai=False)
            
            segments = {}
            for customer, analysis in zip(customers, analyses):
                segment = analysis.segment.value
                if segment not in segments:
                    segments[segment] = {
                        "name": CUSTOMER_SEGMENTS.get(segment, {}).get("name", segment),
                        "description": CUSTOMER_SEGMENTS.get(segment, {}).get("description", ""),
                        "count": 0,
                        "customers": [],
                    }
                segments[segment]["count"] += 1
                segments[segment]["customers"].append({
                    "customer_id": customer.customer_id,
                    "name": customer.name,
                    "email": customer.email,
                    "priority": analysis.priority,
                })
            
            return {
                "segments": segments,
                "total": len(customers),
            }
        finally:
            db.close()
    
    def update_customer_segment(
        self,
        customer_id: int,
        segment: str,
    ) -> dict:
        """Update a customer's segment manually."""
        db = next(get_db())
        try:
            repo = CustomerRepository(db)
            customer = repo.get_by_id(customer_id)
            if not customer:
                return {"success": False, "error": "Customer not found"}
            
            try:
                segment_enum = CustomerSegment(segment)
            except ValueError:
                return {"success": False, "error": f"Invalid segment: {segment}"}
            
            customer.customer_segment = segment_enum
            customer.updated_at = datetime.now()
            repo.update(customer)
            db.commit()
            
            return {"success": True, "message": f"Segment updated to {segment}"}
        except Exception as e:
            logger.error(f"Error updating segment: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()


def create_customer_service(session: Optional[Any] = None) -> CustomerService:
    """Factory function to create customer service."""
    return CustomerService(session)