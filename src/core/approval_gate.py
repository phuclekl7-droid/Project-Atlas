"""
Human-in-the-loop Approval Gate (Feature #68).
Adds an approval step before executing dangerous actions.

Provides:
- Action categorization: safe, confirm, dangerous
- Approval queue management
- Timeout for pending approvals
- Integration with Workflow

Usage:
    gate = ApprovalGate()
    gate.request_approval("delete_file", {"path": "/tmp/test.txt"}, session_id="abc")
    status = gate.get_approval_status("req_123")  # pending, approved, rejected, expired
    gate.approve("req_123")  # Approve the action
    gate.reject("req_123")   # Reject the action
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.core import setup_logger

logger = setup_logger("approval_gate")


class ActionCategory(Enum):
    """Danger level of an action."""
    SAFE = "safe"           # No approval needed
    CONFIRM = "confirm"     # Simple confirmation needed
    DANGEROUS = "dangerous" # Explicit approval needed


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """A request for human approval before executing an action."""

    id: str = ""
    action: str = ""          # Action type (e.g., "delete_file", "run_command")
    params: dict = field(default_factory=dict)  # Action parameters
    description: str = ""     # Human-readable description
    session_id: str = ""      # Session that initiated the request
    category: ActionCategory = ActionCategory.CONFIRM
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: float = 0.0
    expires_at: float = 0.0
    reason: str = ""          # Approval/rejection reason

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def is_resolved(self) -> bool:
        return self.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED)


class ApprovalGate:
    """
    Manages human-in-the-loop approval requests.

    Dangerous actions require human approval before execution.
    Request can time out after configurable TTL.

    Usage:
        gate = ApprovalGate()

        # Request approval (returns request_id)
        req_id = gate.request_approval(
            action="run_command",
            params={"command": "rm -rf /"},
            description="Delete all files?",
        )

        # Check and act
        result = gate.check_and_execute(req_id, actual_execution_fn)
        if result.allowed:
            # Execute approved/rejected action
            pass
    """

    def __init__(self, default_ttl: int = 300, max_pending: int = 50):
        """
        Initialize the approval gate.

        Args:
            default_ttl: Default time-to-live for pending requests in seconds (default: 5 min)
            max_pending: Maximum number of pending requests
        """
        self._default_ttl = default_ttl
        self._max_pending = max_pending
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = False  # Simple flag, not thread-safe but adequate for Streamlit

    def request_approval(
        self,
        action: str,
        params: Optional[dict] = None,
        description: str = "",
        session_id: str = "",
        category: ActionCategory = ActionCategory.CONFIRM,
        ttl: Optional[int] = None,
    ) -> str:
        """
        Request human approval for an action.

        Args:
            action: Action type identifier
            params: Action parameters
            description: Human-readable description
            session_id: Session context
            category: Danger level category
            ttl: Custom TTL in seconds (defaults to self._default_ttl)

        Returns:
            Request ID string (for use in approve/reject)
        """
        # Clean expired requests
        self._clean_expired()

        # Check capacity
        active = sum(1 for r in self._requests.values() if r.status == ApprovalStatus.PENDING)
        if active >= self._max_pending:
            oldest = min(
                (r for r in self._requests.values() if r.status == ApprovalStatus.PENDING),
                key=lambda r: r.created_at,
                default=None,
            )
            if oldest:
                oldest.status = ApprovalStatus.EXPIRED
                logger.info(f"Approval request {oldest.id} expired (queue full)")

        req_id = f"req_{uuid.uuid4().hex[:8]}"
        now = time.time()

        request = ApprovalRequest(
            id=req_id,
            action=action,
            params=params or {},
            description=description,
            session_id=session_id,
            category=category,
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=now + (ttl or self._default_ttl),
        )
        self._requests[req_id] = request
        logger.info(f"Approval requested: {req_id} (action={action}, category={category.value})")

        return req_id

    def approve(self, request_id: str, reason: str = "") -> bool:
        """Approve a pending request. Returns True if approved."""
        req = self._requests.get(request_id)
        if req is None:
            logger.warning(f"Approval request {request_id} not found")
            return False
        if req.status != ApprovalStatus.PENDING:
            return False
        if req.expired:
            req.status = ApprovalStatus.EXPIRED
            return False

        req.status = ApprovalStatus.APPROVED
        req.reason = reason or "Approved"
        logger.info(f"Approval granted: {request_id} ({req.action})")
        return True

    def reject(self, request_id: str, reason: str = "") -> bool:
        """Reject a pending request. Returns True if rejected."""
        req = self._requests.get(request_id)
        if req is None:
            logger.warning(f"Approval request {request_id} not found")
            return False
        if req.status != ApprovalStatus.PENDING:
            return False

        req.status = ApprovalStatus.REJECTED
        req.reason = reason or "Rejected"
        logger.info(f"Approval rejected: {request_id} ({req.action})")
        return True

    def get_status(self, request_id: str) -> Optional[ApprovalStatus]:
        """Get the current status of an approval request."""
        req = self._requests.get(request_id)
        if req is None:
            return None
        if req.expired and req.status == ApprovalStatus.PENDING:
            req.status = ApprovalStatus.EXPIRED
        return req.status

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get a request by ID, auto-expiring if needed."""
        req = self._requests.get(request_id)
        if req is None:
            return None
        if req.expired and req.status == ApprovalStatus.PENDING:
            req.status = ApprovalStatus.EXPIRED
        return req

    def check_and_execute(
        self,
        request_id: str,
        execute_fn: callable,
    ) -> dict:
        """
        Check approval status and execute if approved.

        Args:
            request_id: The approval request ID
            execute_fn: Function to call if approved, receives request params

        Returns:
            dict with keys: allowed (bool), result (any), error (str)
        """
        status = self.get_status(request_id)
        if status is None:
            return {"allowed": False, "result": None, "error": "Request not found"}
        if status == ApprovalStatus.APPROVED:
            try:
                req = self._requests[request_id]
                result = execute_fn(**req.params)
                return {"allowed": True, "result": result, "error": None}
            except Exception as e:
                return {"allowed": True, "result": None, "error": str(e)}
        elif status == ApprovalStatus.REJECTED:
            req = self._requests[request_id]
            return {"allowed": False, "result": None, "error": f"Rejected: {req.reason}"}
        elif status == ApprovalStatus.EXPIRED:
            return {"allowed": False, "result": None, "error": "Request expired"}
        else:
            return {"allowed": False, "result": None, "error": "Request pending"}

    def list_pending(self, session_id: Optional[str] = None) -> list[ApprovalRequest]:
        """List all pending approval requests."""
        self._clean_expired()
        pending = [
            r for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        ]
        if session_id:
            pending = [r for r in pending if r.session_id == session_id]
        return sorted(pending, key=lambda r: r.created_at)

    def list_history(self, limit: int = 20) -> list[ApprovalRequest]:
        """List resolved approval requests (approved, rejected, expired)."""
        resolved = [
            r for r in self._requests.values()
            if r.status != ApprovalStatus.PENDING
        ]
        return sorted(resolved, key=lambda r: r.created_at, reverse=True)[:limit]

    def _clean_expired(self) -> int:
        """Expire all overdue pending requests. Returns count expired."""
        now = time.time()
        count = 0
        for req in self._requests.values():
            if req.status == ApprovalStatus.PENDING and now > req.expires_at:
                req.status = ApprovalStatus.EXPIRED
                count += 1
        if count:
            logger.debug(f"Expired {count} approval requests")
        return count

    def get_stats(self) -> dict:
        """Get approval gate statistics."""
        total = len(self._requests)
        pending = sum(1 for r in self._requests.values() if r.status == ApprovalStatus.PENDING)
        approved = sum(1 for r in self._requests.values() if r.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for r in self._requests.values() if r.status == ApprovalStatus.REJECTED)
        expired = sum(1 for r in self._requests.values() if r.status == ApprovalStatus.EXPIRED)
        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "expired": expired,
        }
