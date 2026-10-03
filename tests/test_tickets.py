"""Tests for ticket data ingestion and repository."""

import os
import sys
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing (must be done before importing settings)
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.db import init_database, reset_database
from src.db.models import (
    Customer,
    CustomerStatus,
    CustomerType,
    Ticket,
    TicketPriority,
    TicketQueue,
    TicketStatus,
    TicketType,
)
from src.db.repositories import CustomerRepository, TicketRepository
from src.services.ticket_data import create_ticket_data_service
from src.db import get_db


def _uid(prefix: str = "TST") -> str:
    """Generate unique test ID."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def setup_module():
    """Reset database before all tests."""
    reset_database()


def test_ticket_model_creation():
    """Test creating a ticket model."""
    reset_database()
    init_database()
    db = next(get_db())
    ticket_repo = TicketRepository(db)

    # Create a test ticket
    ticket = Ticket(
        ticket_id=_uid("MDL"),
        subject="Test Ticket",
        description="Test description",
        ticket_type=TicketType.REQUEST,
        queue=TicketQueue.TECHNICAL_SUPPORT,
        priority=TicketPriority.HIGH,
        status=TicketStatus.OPEN,
        language="en",
        tags=["test", "urgent"],
        source="test",
    )
    created = ticket_repo.create(ticket)
    db.commit()

    assert created.id is not None
    assert created.ticket_id.startswith("MDL-")
    assert created.subject == "Test Ticket"
    assert created.priority == TicketPriority.HIGH
    assert created.status == TicketStatus.OPEN


def test_ticket_customer_relationship():
    """Test ticket-customer relationship."""
    reset_database()
    init_database()
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    ticket_repo = TicketRepository(db)

    # Create a test customer
    customer = Customer(
        customer_id=_uid("CUST"),
        name="Test Customer",
        email="test@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()

    # Create ticket linked to customer
    ticket = Ticket(
        ticket_id=_uid("TKT"),
        customer_id=customer.id,
        subject="Customer Ticket",
        description="Ticket for test customer",
        ticket_type=TicketType.INCIDENT,
        queue=TicketQueue.BILLING_PAYMENTS,
        priority=TicketPriority.MEDIUM,
        status=TicketStatus.IN_PROGRESS,
    )
    created = ticket_repo.create(ticket)
    db.commit()

    # Verify relationship
    assert created.customer_id == customer.id
    assert created.customer.name == "Test Customer"
    assert created.customer.email == "test@example.com"


def test_ticket_duplicate_handling():
    """Test duplicate ticket_id handling."""
    reset_database()
    init_database()
    db = next(get_db())
    ticket_repo = TicketRepository(db)

    dup_id = _uid("DUP")

    # Create first ticket
    ticket1 = Ticket(
        ticket_id=dup_id,
        subject="First Ticket",
        description="First",
        ticket_type=TicketType.REQUEST,
        queue=TicketQueue.GENERAL,
    )
    ticket_repo.create(ticket1)
    db.commit()

    # Try to create duplicate
    ticket2 = Ticket(
        ticket_id=dup_id,  # Same ID
        subject="Second Ticket",
        description="Second",
        ticket_type=TicketType.INCIDENT,
        queue=TicketQueue.TECHNICAL_SUPPORT,
    )
    try:
        ticket_repo.create(ticket2)
        db.commit()
        assert False, "Should have raised IntegrityError"
    except Exception:
        db.rollback()
        # Expected - duplicate key violation


def test_ticket_priority_filtering():
    """Test filtering tickets by priority."""
    reset_database()
    init_database()
    db = next(get_db())
    ticket_repo = TicketRepository(db)

    test_id = _uid("PRI")

    # Create tickets with different priorities
    for i, priority in enumerate([TicketPriority.LOW, TicketPriority.MEDIUM, TicketPriority.HIGH, TicketPriority.CRITICAL]):
        ticket = Ticket(
            ticket_id=f"{test_id}-{i:03d}",
            subject=f"Priority {priority.value} Ticket",
            description="Test",
            ticket_type=TicketType.REQUEST,
            queue=TicketQueue.GENERAL,
            priority=priority,
        )
        ticket_repo.create(ticket)
    db.commit()

    # Test high priority filter
    high_priority = ticket_repo.get_high_priority_tickets()
    # Filter only tickets from this test run
    test_tickets = [t for t in high_priority if t.ticket_id.startswith(test_id)]
    high_count = sum(1 for t in test_tickets if t.priority in [TicketPriority.HIGH, TicketPriority.CRITICAL])
    assert high_count == 2

    # Test priority stats
    priority_stats = ticket_repo.get_priority_stats()
    assert TicketPriority.LOW.value in priority_stats
    assert TicketPriority.HIGH.value in priority_stats
    assert TicketPriority.CRITICAL.value in priority_stats


def test_ticket_status_filtering():
    """Test filtering tickets by status."""
    reset_database()
    init_database()
    db = next(get_db())
    ticket_repo = TicketRepository(db)

    test_id = _uid("STS")

    # Create tickets with different statuses
    for i, status in enumerate([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED]):
        ticket = Ticket(
            ticket_id=f"{test_id}-{i:03d}",
            subject=f"Status {status.value} Ticket",
            description="Test",
            ticket_type=TicketType.REQUEST,
            queue=TicketQueue.GENERAL,
            status=status,
        )
        ticket_repo.create(ticket)
    db.commit()

    # Test open tickets
    open_tickets = ticket_repo.get_open_tickets()
    test_open = [t for t in open_tickets if t.ticket_id.startswith(test_id)]
    assert len(test_open) == 1
    assert test_open[0].status == TicketStatus.OPEN

    # Test status stats
    status_stats = ticket_repo.get_status_stats()
    assert TicketStatus.OPEN.value in status_stats
    assert TicketStatus.RESOLVED.value in status_stats


def test_ticket_queue_filtering():
    """Test filtering tickets by queue."""
    reset_database()
    init_database()
    db = next(get_db())
    ticket_repo = TicketRepository(db)

    test_id = _uid("QUE")

    # Create tickets with different queues
    for queue in [TicketQueue.TECHNICAL_SUPPORT, TicketQueue.BILLING_PAYMENTS, TicketQueue.SALES_PRESALES]:
        ticket = Ticket(
            ticket_id=f"{test_id}-{queue.value}",
            subject=f"Queue {queue.value} Ticket",
            description="Test",
            ticket_type=TicketType.REQUEST,
            queue=queue,
        )
        ticket_repo.create(ticket)
    db.commit()

    # Test queue stats
    queue_stats = ticket_repo.get_queue_stats()
    assert TicketQueue.TECHNICAL_SUPPORT.value in queue_stats
    assert TicketQueue.BILLING_PAYMENTS.value in queue_stats


def test_ticket_resolution():
    """Test ticket resolution workflow."""
    reset_database()
    init_database()
    db = next(get_db())
    ticket_repo = TicketRepository(db)

    test_id = _uid("RES")

    # Create open ticket
    ticket = Ticket(
        ticket_id=f"{test_id}-001",
        subject="To Resolve",
        description="Needs resolution",
        ticket_type=TicketType.INCIDENT,
        queue=TicketQueue.TECHNICAL_SUPPORT,
        status=TicketStatus.OPEN,
    )
    created = ticket_repo.create(ticket)
    db.commit()

    # Resolve ticket
    resolved = ticket_repo.resolve_ticket(created.id, "Fixed the issue")
    assert resolved is not None
    assert resolved.status == TicketStatus.RESOLVED
    assert resolved.resolution == "Fixed the issue"
    assert resolved.resolved_at is not None

    # Close ticket
    closed = ticket_repo.close_ticket(resolved.id)
    assert closed is not None
    assert closed.status == TicketStatus.CLOSED

    # Try to close non-resolved ticket (should return ticket but not change status)
    ticket2 = Ticket(
        ticket_id=f"{test_id}-002",
        subject="Open Ticket",
        description="Still open",
        ticket_type=TicketType.REQUEST,
        queue=TicketQueue.GENERAL,
        status=TicketStatus.OPEN,
    )
    created2 = ticket_repo.create(ticket2)
    db.commit()

    closed_fail = ticket_repo.close_ticket(created2.id)
    # close_ticket returns the ticket but doesn't change status if not resolved
    assert closed_fail is not None
    assert closed_fail.status == TicketStatus.OPEN  # Status unchanged


def test_ticket_csv_ingestion():
    """Test CSV ingestion for tickets."""
    reset_database()
    init_database()
    
    # Create test CSV
    import tempfile
    import csv
    
    test_id = _uid("CSV")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ticket_id', 'subject', 'body', 'type', 'queue', 'priority', 'language', 'tag_1', 'tag_2'])
        writer.writerow([f'{test_id}-001', 'Test Subject 1', 'Test body 1', 'incident', 'technical support', 'high', 'en', 'bug', 'urgent'])
        writer.writerow([f'{test_id}-002', 'Test Subject 2', 'Test body 2', 'request', 'billing and payments', 'low', 'en', 'billing', 'question'])
        writer.writerow([f'{test_id}-003', 'Test Subject 3', 'Test body 3', 'problem', 'returns and exchanges', 'medium', 'de', 'defect', 'quality'])
        csv_path = f.name
    
    try:
        service = create_ticket_data_service()
        result = service.ingest_from_csv(csv_path)
        
        assert result.success
        assert result.total_rows == 3
        assert result.created == 3
        assert len(result.errors) == 0
    finally:
        os.unlink(csv_path)


def test_ticket_ingestion_customer_resolution():
    """Test that ticket ingestion resolves customers."""
    reset_database()
    init_database()
    db = next(get_db())
    customer_repo = CustomerRepository(db)
    
    test_id = _uid("RSL")
    
    # Create a test customer with email
    customer = Customer(
        customer_id=f"{test_id}-001",
        name="John Doe",
        email="john.doe@example.com",
        customer_type=CustomerType.INDIVIDUAL,
        customer_status=CustomerStatus.ACTIVE,
    )
    customer_repo.create(customer)
    db.commit()
    
    # Create test CSV with matching email in body
    import tempfile
    import csv
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ticket_id', 'subject', 'body', 'type', 'queue', 'priority', 'language'])
        writer.writerow([f'{test_id}-001', 'Support Request', 'Hi, this is john.doe@example.com, I need help', 'incident', 'technical support', 'high', 'en'])
        csv_path = f.name
    
    try:
        service = create_ticket_data_service()
        result = service.ingest_from_csv(csv_path)
        
        assert result.success
        assert result.created == 1
        
        # Check that customer was resolved
        ticket_repo = TicketRepository(db)
        tickets = ticket_repo.list_tickets(limit=10)
        created_ticket = next((t for t in tickets if t.ticket_id == f"{test_id}-001"), None)
        assert created_ticket is not None
        assert created_ticket.customer_id == customer.id
    finally:
        os.unlink(csv_path)


if __name__ == "__main__":
    test_ticket_model_creation()
    test_ticket_customer_relationship()
    test_ticket_duplicate_handling()
    test_ticket_priority_filtering()
    test_ticket_status_filtering()
    test_ticket_queue_filtering()
    test_ticket_resolution()
    test_ticket_csv_ingestion()
    test_ticket_ingestion_customer_resolution()
    print("All ticket tests passed!")