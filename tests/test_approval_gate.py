"""
Tests for Feature #68: Human-in-the-loop Approval Gate.
"""

import time

import pytest

from src.core.approval_gate import (
    ApprovalGate,
    ApprovalRequest,
    ActionCategory,
    ApprovalStatus,
)


class TestApprovalGate:
    """Tests for the ApprovalGate class."""

    def test_request_approval(self):
        gate = ApprovalGate()
        req_id = gate.request_approval(
            action="delete_file",
            params={"path": "/tmp/test.txt"},
            description="Delete test file?",
        )
        assert req_id.startswith("req_")
        status = gate.get_status(req_id)
        assert status == ApprovalStatus.PENDING

    def test_approve_request(self):
        gate = ApprovalGate()
        req_id = gate.request_approval("run_command", {"cmd": "ls"}, "Run ls")
        assert gate.approve(req_id)
        assert gate.get_status(req_id) == ApprovalStatus.APPROVED

    def test_reject_request(self):
        gate = ApprovalGate()
        req_id = gate.request_approval("run_command", {"cmd": "rm"}, "Remove files?")
        assert gate.reject(req_id)
        assert gate.get_status(req_id) == ApprovalStatus.REJECTED

    def test_approve_nonexistent(self):
        gate = ApprovalGate()
        assert not gate.approve("nonexistent_id")

    def test_reject_nonexistent(self):
        gate = ApprovalGate()
        assert not gate.reject("nonexistent_id")

    def test_double_approve_fails(self):
        gate = ApprovalGate()
        req_id = gate.request_approval("test", {}, "test")
        assert gate.approve(req_id)
        assert not gate.approve(req_id)  # Already approved

    def test_double_reject_fails(self):
        gate = ApprovalGate()
        req_id = gate.request_approval("test", {}, "test")
        assert gate.reject(req_id)
        assert not gate.reject(req_id)  # Already rejected

    def test_auto_expire(self):
        gate = ApprovalGate(default_ttl=0)  # Immediate expiry
        req_id = gate.request_approval("test", {}, "test")
        time.sleep(0.01)  # Tiny delay
        status = gate.get_status(req_id)
        assert status == ApprovalStatus.EXPIRED

    def test_list_pending(self):
        gate = ApprovalGate()
        req1 = gate.request_approval("action1", {}, "test1")
        req2 = gate.request_approval("action2", {}, "test2")
        gate.approve(req1)
        pending = gate.list_pending()
        assert len(pending) == 1
        assert pending[0].id == req2

    def test_list_pending_by_session(self):
        gate = ApprovalGate()
        gate.request_approval("action1", {}, "test1", session_id="sess_a")
        gate.request_approval("action2", {}, "test2", session_id="sess_b")
        pending_a = gate.list_pending(session_id="sess_a")
        assert len(pending_a) == 1

    def test_list_history(self):
        gate = ApprovalGate()
        req1 = gate.request_approval("a1", {}, "t1")
        req2 = gate.request_approval("a2", {}, "t2")
        gate.approve(req1)
        gate.reject(req2)
        history = gate.list_history()
        assert len(history) == 2

    def test_get_request_nonexistent(self):
        gate = ApprovalGate()
        req = gate.get_request("nonexistent")
        assert req is None

    def test_check_and_execute_approved(self):
        gate = ApprovalGate()
        req_id = gate.request_approval("custom", {"x": 5}, "Multiply")
        gate.approve(req_id)
        result = gate.check_and_execute(req_id, lambda x: x * 2)
        assert result["allowed"]
        assert result["result"] == 10

    def test_check_and_execute_rejected(self):
        gate = ApprovalGate()
        req_id = gate.request_approval("test", {}, "Test")
        gate.reject(req_id, reason="Not needed")
        result = gate.check_and_execute(req_id, lambda: "done")
        assert not result["allowed"]
        assert "Not needed" in result["error"]

    def test_check_and_execute_pending(self):
        gate = ApprovalGate()
        req_id = gate.request_approval("test", {}, "Test")
        result = gate.check_and_execute(req_id, lambda: "done")
        assert not result["allowed"]
        assert "pending" in result["error"].lower()

    def test_get_stats(self):
        gate = ApprovalGate()
        stats = gate.get_stats()
        assert stats["total"] == 0
        assert stats["pending"] == 0

        gate.request_approval("test", {}, "test")
        stats = gate.get_stats()
        assert stats["total"] == 1
        assert stats["pending"] == 1
