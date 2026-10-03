"""Customer Follow-up Manager Service for intelligent follow-up workflows."""

from datetime import datetime, timezone
from typing import Optional, List

from src.config.logging_config import logger
from src.db import db_service
from src.db.models import FollowUp, FollowUpStatus, Task, Customer
from src.db.repositories import FollowUpRepository, TaskRepository, CustomerRepository


class FollowUpTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""
    pass


class FollowUpService:
    """Service for managing customer follow-ups with status validation."""
    
    # Valid status transitions
    VALID_TRANSITIONS = {
        FollowUpStatus.PENDING: [
            FollowUpStatus.IN_PROGRESS,
            FollowUpStatus.WAITING_APPROVAL,
            FollowUpStatus.CANCELLED,
        ],
        FollowUpStatus.IN_PROGRESS: [
            FollowUpStatus.COMPLETED,
            FollowUpStatus.WAITING_APPROVAL,
            FollowUpStatus.CANCELLED,
        ],
        FollowUpStatus.WAITING_APPROVAL: [
            FollowUpStatus.IN_PROGRESS,
            FollowUpStatus.COMPLETED,
            FollowUpStatus.CANCELLED,
        ],
        FollowUpStatus.COMPLETED: [],  # Terminal state
        FollowUpStatus.CANCELLED: [],  # Terminal state
        FollowUpStatus.OVERDUE: [
            FollowUpStatus.IN_PROGRESS,
            FollowUpStatus.WAITING_APPROVAL,
            FollowUpStatus.CANCELLED,
        ],
    }
    
    def __init__(self):
        """Initialize follow-up service."""
        pass
    
    def _get_session(self):
        """Get a fresh database session."""
        return db_service.get_session()
    
    def _execute_in_transaction(self, func):
        """Execute a function within a database transaction."""
        session = db_service.get_session()
        try:
            result = func(session)
            session.commit()
            # Only expunge single SQLAlchemy model instances, not lists
            if result is not None and hasattr(result, '__table__'):
                session.refresh(result)
                session.expunge(result)
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def _validate_transition(self, current_status: FollowUpStatus, new_status: FollowUpStatus) -> None:
        """Validate that a status transition is allowed."""
        if current_status == new_status:
            return
        allowed = self.VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise FollowUpTransitionError(
                f"Invalid status transition from {current_status.value} to {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
    
    def create_follow_up(
        self,
        customer_id: int,
        reason: str,
        due_date: datetime,
        title: Optional[str] = None,
        priority: int = 0,
        assigned_task_id: Optional[int] = None,
        last_contact_date: Optional[datetime] = None,
        next_action: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> FollowUp:
        """Create a new follow-up."""
        if not customer_id:
            raise ValueError("customer_id is required")
        if not reason or not reason.strip():
            raise ValueError("reason is required")
        if not due_date:
            raise ValueError("due_date is required")
        # Handle naive datetimes by assuming UTC
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        if due_date < datetime.now(timezone.utc):
            raise ValueError("due_date must be in the future")
        if priority < 0 or priority > 100:
            raise ValueError("priority must be between 0 and 100")
        
        return self._execute_in_transaction(lambda session: self._create_follow_up_in_session(
            session, customer_id, reason, due_date, title, priority, 
            assigned_task_id, last_contact_date, next_action, metadata
        ))
    
    def _create_follow_up_in_session(
        self,
        session,
        customer_id: int,
        reason: str,
        due_date: datetime,
        title: Optional[str] = None,
        priority: int = 0,
        assigned_task_id: Optional[int] = None,
        last_contact_date: Optional[datetime] = None,
        next_action: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> FollowUp:
        """Create a new follow-up within an existing session."""
        # Resolve customer_id string to internal integer ID
        customer_repo = CustomerRepository(session)
        customer = None
        if isinstance(customer_id, str):
            customer = customer_repo.get_by_customer_id(customer_id)
        else:
            customer = session.get(Customer, customer_id)
        
        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")
        
        internal_customer_id = customer.id
        
        repo = FollowUpRepository(session)
        
        # Auto-generate title from reason if not provided
        if not title:
            title = reason[:100] + ("..." if len(reason) > 100 else "")
        
        follow_up = FollowUp(
            customer_id=internal_customer_id,
            title=title,
            reason=reason.strip(),
            priority=priority,
            status=FollowUpStatus.PENDING,
            due_date=due_date,
            assigned_task_id=assigned_task_id,
            last_contact_date=last_contact_date,
            next_action=next_action.strip() if next_action else None,
            follow_up_metadata=metadata,
        )
        
        result = repo.create(follow_up)
        logger.info(f"Created follow-up {result.id} for customer {internal_customer_id}")
        return result
    
    def get_follow_up(self, follow_up_id: int) -> Optional[FollowUp]:
        """Get follow-up by ID."""
        return self._execute_in_transaction(
            lambda session: FollowUpRepository(session).get_by_id(follow_up_id)
        )
    
    def get_follow_up_by_id(self, follow_up_id: int) -> Optional[FollowUp]:
        """Alias for get_follow_up for API consistency."""
        return self.get_follow_up(follow_up_id)
    
    def list_follow_ups(
        self,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[FollowUp]:
        """List follow-ups with optional filters."""
        def _list(session):
            repo = FollowUpRepository(session)
            status_enum = None
            if status:
                try:
                    status_enum = FollowUpStatus(status)
                except ValueError:
                    raise ValueError(f"Invalid status: {status}")
            approvals = repo.list_follow_ups(
                customer_id=customer_id,
                status=status_enum,
                skip=skip,
                limit=limit,
            )
            # Expunge each item to avoid DetachedInstanceError
            for approval in approvals:
                session.expunge(approval)
            return approvals
        return self._execute_in_transaction(_list)
    
    def update_status(self, follow_up_id: int, new_status: str) -> FollowUp:
        """Update follow-up status with transition validation."""
        def _update(session):
            repo = FollowUpRepository(session)
            follow_up = repo.get_by_id(follow_up_id)
            if not follow_up:
                raise ValueError(f"Follow-up {follow_up_id} not found")
            
            try:
                new_status_enum = FollowUpStatus(new_status)
            except ValueError:
                raise ValueError(f"Invalid status: {new_status}")
            
            self._validate_transition(follow_up.status, new_status_enum)
            
            follow_up.status = new_status_enum
            if new_status_enum == FollowUpStatus.COMPLETED:
                follow_up.completed_at = datetime.now(timezone.utc)
            
            result = repo.update(follow_up)
            logger.info(f"Updated follow-up {follow_up_id} status to {new_status}")
            return result
        
        return self._execute_in_transaction(_update)
    
    def mark_overdue(self, follow_up_id: int) -> FollowUp:
        """Mark a follow-up as overdue."""
        return self.update_status(follow_up_id, FollowUpStatus.OVERDUE.value)
    
    def get_overdue_follow_ups(self) -> List[FollowUp]:
        """Get all overdue follow-ups."""
        return self._execute_in_transaction(
            lambda session: FollowUpRepository(session).get_overdue_follow_ups()
        )
    
    def get_todays_follow_ups(self) -> List[FollowUp]:
        """Get follow-ups due today."""
        return self._execute_in_transaction(
            lambda session: FollowUpRepository(session).get_todays_follow_ups()
        )
    
    def get_upcoming_follow_ups(self, days: int = 7) -> List[FollowUp]:
        """Get upcoming follow-ups within specified days."""
        return self._execute_in_transaction(
            lambda session: FollowUpRepository(session).get_upcoming_follow_ups(days=days)
        )
    
    def get_high_priority_follow_ups(self, min_priority: int = 50) -> List[FollowUp]:
        """Get high-priority follow-ups."""
        return self._execute_in_transaction(
            lambda session: FollowUpRepository(session).get_high_priority_follow_ups(min_priority=min_priority)
        )
    
    def get_customer_follow_ups(self, customer_id: int, status: Optional[str] = None) -> List[FollowUp]:
        """Get all follow-ups for a specific customer."""
        def _get(session):
            repo = FollowUpRepository(session)
            status_enum = None
            if status:
                try:
                    status_enum = FollowUpStatus(status)
                except ValueError:
                    raise ValueError(f"Invalid status: {status}")
            return repo.list_follow_ups(customer_id=customer_id, status=status_enum)
        return self._execute_in_transaction(_get)
    
    def update_follow_up(
        self,
        follow_up_id: int,
        title: Optional[str] = None,
        reason: Optional[str] = None,
        priority: Optional[int] = None,
        due_date: Optional[datetime] = None,
        assigned_task_id: Optional[int] = None,
        next_action: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> FollowUp:
        """Update follow-up fields (excluding status)."""
        def _update(session):
            repo = FollowUpRepository(session)
            follow_up = repo.get_by_id(follow_up_id)
            if not follow_up:
                raise ValueError(f"Follow-up {follow_up_id} not found")
            
            if title is not None:
                follow_up.title = title
            if reason is not None:
                follow_up.reason = reason.strip()
            if priority is not None:
                if priority < 0 or priority > 100:
                    raise ValueError("priority must be between 0 and 100")
                follow_up.priority = priority
            if due_date is not None:
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=timezone.utc)
                if due_date < datetime.now(timezone.utc):
                    raise ValueError("due_date must be in the future")
                follow_up.due_date = due_date
            if assigned_task_id is not None:
                follow_up.assigned_task_id = assigned_task_id
            if next_action is not None:
                follow_up.next_action = next_action.strip() if next_action else None
            if metadata is not None:
                follow_up.follow_up_metadata = metadata
            
            follow_up.updated_at = datetime.now(timezone.utc)
            return repo.update(follow_up)
        
        return self._execute_in_transaction(_update)
    
    def delete_follow_up(self, follow_up_id: int) -> bool:
        """Delete a follow-up by ID."""
        def _delete(session):
            repo = FollowUpRepository(session)
            return repo.delete(follow_up_id)
        return self._execute_in_transaction(_delete)


def create_follow_up_service() -> FollowUpService:
    """Factory function to create follow-up service."""
    return FollowUpService()
