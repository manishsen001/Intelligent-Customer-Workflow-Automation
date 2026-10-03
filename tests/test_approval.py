"""Tests for approval system."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set dummy API key for testing
import os
os.environ["NVIDIA_API_KEY"] = "test-key-for-testing"

from src.db import init_database, db_service
from src.db.models import ApprovalStatus
from src.services.approval import create_approval_service


def get_test_db():
    """Get a test database session."""
    return db_service.get_session()


def test_approval_creation():
    """Test creating an approval."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        approval = service.create_approval(
            approval_type="send_email",
            title="Test Email Approval",
            description="Approval for test email",
            content={"subject": "Test", "body": "Test body"},
            requested_by="test_user",
        )
        
        assert approval.id is not None
        assert approval.approval_type == "send_email"
        assert approval.title == "Test Email Approval"
        assert approval.status.value == "pending"
        assert approval.requested_by == "test_user"
        
        print("✓ Approval creation test passed")
    finally:
        db.close()


def test_approval_approve():
    """Test approving an approval."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        approval = service.create_approval(
            approval_type="send_email",
            title="Test Approval",
            description="Test",
            content={},
        )
        
        approved = service.approve(approval.id, "reviewer", "Looks good")
        
        assert approved.status == ApprovalStatus.APPROVED
        assert approved.approved_by == "reviewer"
        assert approved.approved_at is not None
        
        print("✓ Approval approve test passed")
    finally:
        db.close()


def test_approval_reject():
    """Test rejecting an approval."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        approval = service.create_approval(
            approval_type="send_email",
            title="Test Rejection",
            description="Test",
            content={},
        )
        
        rejected = service.reject(approval.id, "reviewer", "Not appropriate")
        
        assert rejected.status == ApprovalStatus.REJECTED
        assert rejected.rejection_reason == "Not appropriate"
        assert rejected.approved_by == "reviewer"
        
        print("✓ Approval reject test passed")
    finally:
        db.close()


def test_approval_edit():
    """Test editing an approval."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        approval = service.create_approval(
            approval_type="send_email",
            title="Test Edit",
            description="Test",
            content={"subject": "Original"},
        )
        
        edited = service.edit(approval.id, "editor", {"subject": "Updated"}, "Updated subject")
        
        assert edited.status == ApprovalStatus.EDITED
        assert edited.content == {"subject": "Updated"}
        
        print("✓ Approval edit test passed")
    finally:
        db.close()


def test_invalid_transitions():
    """Test invalid approval state transitions."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        approval = service.create_approval(
            approval_type="send_email",
            title="Test Invalid",
            description="Test",
            content={},
        )
        
        # Approve first
        service.approve(approval.id, "reviewer")
        
        # Try to approve again - should fail
        try:
            service.approve(approval.id, "reviewer")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Cannot approve" in str(e)
        
        # Create new approval and reject
        approval2 = service.create_approval(
            approval_type="send_email",
            title="Test Reject",
            description="Test",
            content={},
        )
        service.reject(approval2.id, "reviewer", "Reason")
        
        # Try to edit rejected - should fail
        try:
            service.edit(approval2.id, "editor", {}, "comment")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Cannot edit" in str(e)
        
        print("✓ Invalid transitions test passed")
    finally:
        db.close()


def test_bulk_operations():
    """Test bulk approve/reject."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        # Create multiple approvals
        approval_ids = []
        for i in range(3):
            approval = service.create_approval(
                approval_type="send_email",
                title=f"Bulk Test {i}",
                description="Test",
                content={},
            )
            approval_ids.append(approval.id)
        
        # Bulk approve
        approved = service.approve_all(approval_ids, "reviewer")
        assert len(approved) == 3
        assert all(a.status == ApprovalStatus.APPROVED for a in approved)
        
        # Create more for reject
        reject_ids = []
        for i in range(2):
            approval = service.create_approval(
                approval_type="bulk_email",
                title=f"Bulk Reject {i}",
                description="Test",
                content={},
            )
            reject_ids.append(approval.id)
        
        rejected = service.reject_all(reject_ids, "reviewer", "Bulk reject reason")
        assert len(rejected) == 2
        assert all(r.status == ApprovalStatus.REJECTED for r in rejected)
        assert all(r.rejection_reason == "Bulk reject reason" for r in rejected)
        
        print("✓ Bulk operations test passed")
    finally:
        db.close()


def test_approval_listing():
    """Test listing approvals with filters."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        # Create approvals with different statuses
        service.create_approval("type1", "Pending 1", "Desc", {}, requested_by="user1")
        a2 = service.create_approval("type1", "Pending 2", "Desc", {}, requested_by="user1")
        service.approve(a2.id, "reviewer")
        
        a3 = service.create_approval("type2", "Pending 3", "Desc", {}, requested_by="user2")
        service.reject(a3.id, "reviewer", "Reason")
        
        # List all (3 created in this test + potentially from other tests)
        all_approvals = service.list_approvals(limit=100)
        assert len(all_approvals) >= 3
        
        # List pending
        pending = service.list_approvals(status=ApprovalStatus.PENDING, limit=100)
        assert all(a.status == ApprovalStatus.PENDING for a in pending)
        assert len(pending) >= 1
        
        # List approved
        approved = service.list_approvals(status=ApprovalStatus.APPROVED, limit=100)
        assert all(a.status == ApprovalStatus.APPROVED for a in approved)
        assert len(approved) >= 1
        
        # List rejected
        rejected = service.list_approvals(status=ApprovalStatus.REJECTED, limit=100)
        assert all(a.status == ApprovalStatus.REJECTED for a in rejected)
        assert len(rejected) >= 1
        
        print("✓ Approval listing test passed")
    finally:
        db.close()


def test_approval_stats():
    """Test approval statistics."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        stats = service.get_approval_stats()
        
        assert "total" in stats
        assert "pending" in stats
        assert "approved" in stats
        assert "rejected" in stats
        assert "edited" in stats
        assert "by_type" in stats
        
        print("✓ Approval stats test passed")
    finally:
        db.close()


def test_approval_workflow_integration():
    """Test approval with workflow execution ID."""
    init_database()
    db = get_test_db()
    try:
        service = create_approval_service(db)
        
        approval = service.create_approval(
            approval_type="send_email",
            title="Workflow Integration",
            description="Test workflow integration",
            content={"emails": [{"to": "test@test.com"}]},
            workflow_execution_id=123,
        )
        
        assert approval.workflow_execution_id == 123
        
        approved = service.approve(approval.id, "reviewer")
        assert approved.workflow_execution_id == 123
        
        print("✓ Approval workflow integration test passed")
    finally:
        db.close()


if __name__ == "__main__":
    test_approval_creation()
    test_approval_approve()
    test_approval_reject()
    test_approval_edit()
    test_invalid_transitions()
    test_bulk_operations()
    test_approval_listing()
    test_approval_stats()
    test_approval_workflow_integration()
    print("\n✅ All approval tests passed!")