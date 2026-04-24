"""Export operator feedback as a Phoenix-shaped labelled dataset.

Produces a JSON structure with one section per agent type. Each example
carries the original suggestion, the operator decision, and per-example
evaluator metrics. The analyst section also includes an aggregate so
reviewers can see decision_alignment at a glance.

Parser examples are currently empty because we don't have an operator
field-correction flow yet (see evaluators.py).

After building the dataset, the use case marks each included feedback with
`phoenix_label_exported = True` so a future re-run can easily filter to
"new since last export" if desired.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import OperatorDecision
from src.infrastructure.observability.evaluators import analyst_decision_alignment
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportDatasetResult:
    exported_at: datetime
    parser_examples_count: int
    analyst_examples_count: int
    marked_feedback_count: int
    dataset: dict  # Phoenix-shaped JSON


class ExportDatasetUseCase:
    def __init__(
        self,
        session: AsyncSession,
        confidence_threshold: float = 0.9,
    ) -> None:
        self._session = session
        self._confidence_threshold = confidence_threshold

    async def execute(self, *, limit: int = 100) -> ExportDatasetResult:
        rows = (
            await self._session.execute(
                select(Feedback, AgentSuggestion, Order)
                .join(AgentSuggestion, Feedback.agent_suggestion_id == AgentSuggestion.id)
                .join(Order, Feedback.order_id == Order.id)
                .order_by(Feedback.created_at.desc())
                .limit(limit)
            )
        ).all()

        analyst_examples: list[dict] = []
        accepted = 0
        modified = 0
        rejected = 0
        high_conf_overrides = 0

        for feedback, suggestion, order in rows:
            confidence = float(suggestion.confidence)
            evaluation = analyst_decision_alignment(
                suggestion_confidence=confidence,
                operator_decision=feedback.operator_decision,
                confidence_threshold=self._confidence_threshold,
            )

            if feedback.operator_decision == OperatorDecision.ACCEPTED:
                accepted += 1
            elif feedback.operator_decision == OperatorDecision.MODIFIED:
                modified += 1
            elif feedback.operator_decision == OperatorDecision.REJECTED:
                rejected += 1

            if evaluation.high_confidence_override:
                high_conf_overrides += 1

            analyst_examples.append(
                {
                    "orderId": str(order.id),
                    "orderCode": order.code,
                    "suggestion": {
                        "id": str(suggestion.id),
                        "action": suggestion.action.value,
                        "confidence": confidence,
                        "reasoning": suggestion.reasoning,
                        "anomaliesDetected": suggestion.anomalies_detected,
                        "phoenixTraceId": suggestion.phoenix_trace_id,
                    },
                    "feedback": {
                        "id": str(feedback.id),
                        "operatorDecision": feedback.operator_decision.value,
                        "finalAction": feedback.final_action.value,
                        "operatorReason": feedback.operator_reason,
                    },
                    "evaluation": {
                        "aligned": evaluation.aligned,
                        "highConfidenceOverride": evaluation.high_confidence_override,
                    },
                }
            )

        total = len(analyst_examples)
        decision_alignment = accepted / total if total else 0.0

        # Mark feedbacks as exported
        for feedback, _, _ in rows:
            feedback.phoenix_label_exported = True
        await self._session.commit()

        now = datetime.now(UTC)
        dataset = {
            "exportedAt": now.isoformat(),
            "confidenceThreshold": self._confidence_threshold,
            "parserAgent": {
                "examples": [],
                "aggregate": {
                    "totalExamples": 0,
                    "note": (
                        "Parser evaluator requires an operator field-correction "
                        "flow which is not yet implemented."
                    ),
                },
            },
            "analystAgent": {
                "examples": analyst_examples,
                "aggregate": {
                    "totalExamples": total,
                    "acceptedCount": accepted,
                    "modifiedCount": modified,
                    "rejectedCount": rejected,
                    "decisionAlignment": round(decision_alignment, 3),
                    "highConfidenceOverrides": high_conf_overrides,
                },
            },
        }

        return ExportDatasetResult(
            exported_at=now,
            parser_examples_count=0,
            analyst_examples_count=total,
            marked_feedback_count=len(rows),
            dataset=dataset,
        )
