from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    CLARIFICATION_REQUESTED = "clarification_requested"
    ESCALATED = "escalated"
    REJECTED_BY_OPERATOR = "rejected_by_operator"


class AgentAction(StrEnum):
    APPROVE = "approve"
    REQUEST_CLARIFICATION = "request_clarification"
    ESCALATE = "escalate"


class OperatorDecision(StrEnum):
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"
