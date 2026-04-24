"""ExportDatasetUseCase integration test against real DB.

Inserts known feedback data with a deterministic marker (via a unique
retailer_code) so the test's assertions are independent of DB pollution
from other tests.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from src.application.use_cases.export_dataset import ExportDatasetUseCase
from src.domain.enums import AgentAction, OperatorDecision, OrderStatus
from src.infrastructure.persistence.engine import async_session_factory
from src.infrastructure.persistence.models.agent_suggestion import AgentSuggestion
from src.infrastructure.persistence.models.currency import Currency
from src.infrastructure.persistence.models.feedback import Feedback
from src.infrastructure.persistence.models.order import Order
from src.infrastructure.persistence.models.retailer import Retailer
from src.infrastructure.persistence.models.supplier import Supplier


async def _seed_analyst_sample(
    *,
    operator_decision: OperatorDecision,
    confidence: float,
    retailer_code: str,
) -> tuple[str, str]:
    """Insert one order + suggestion + feedback. Returns (order_id, feedback_id)."""
    async with async_session_factory() as session:
        retailer = Retailer(id=uuid4(), code=retailer_code, name=retailer_code)
        supplier = Supplier(
            id=uuid4(), code=f"S-{uuid4().hex[:6]}", name="Export Supplier"
        )
        currency = (
            await session.execute(select(Currency).where(Currency.code == "EUR"))
        ).scalar_one()
        session.add_all([retailer, supplier])
        await session.flush()

        order = Order(
            id=uuid4(),
            code=f"ORD-EXP-{uuid4().hex[:6]}",
            retailer_id=retailer.id,
            supplier_id=supplier.id,
            order_number="PO-EXP",
            order_date=datetime.now(UTC),
            status=OrderStatus.APPROVED,
            total_amount=5_000,
            currency_id=currency.id,
            raw_payload={"orderNumber": "PO-EXP"},
            documents=[],
        )
        session.add(order)
        suggestion = AgentSuggestion(
            id=uuid4(),
            order_id=order.id,
            agent_type="analyst",
            action=AgentAction.APPROVE,
            confidence=Decimal(str(confidence)),
            reasoning="export-test",
            anomalies_detected=[],
        )
        session.add(suggestion)
        await session.flush()
        feedback = Feedback(
            id=uuid4(),
            order_id=order.id,
            agent_suggestion_id=suggestion.id,
            operator_decision=operator_decision,
            final_action=AgentAction.APPROVE,
            operator_reason="export test",
            anomaly_feedback={},
            phoenix_label_exported=False,
        )
        session.add(feedback)
        await session.commit()
        return str(order.id), str(feedback.id)


@pytest.mark.asyncio
async def test_export_includes_analyst_example_with_evaluation() -> None:
    marker = f"EXPORT-TEST-{uuid4().hex[:8]}"
    order_id, feedback_id = await _seed_analyst_sample(
        operator_decision=OperatorDecision.ACCEPTED,
        confidence=0.95,
        retailer_code=marker,
    )

    async with async_session_factory() as session:
        use_case = ExportDatasetUseCase(session=session, confidence_threshold=0.9)
        result = await use_case.execute(limit=500)

    # Locate our test example in the exported analyst section
    examples = result.dataset["analystAgent"]["examples"]
    our = next(e for e in examples if e["orderId"] == order_id)
    assert our["suggestion"]["action"] == "approve"
    assert our["suggestion"]["confidence"] == pytest.approx(0.95)
    assert our["feedback"]["operatorDecision"] == "accepted"
    assert our["evaluation"]["aligned"] is True
    assert our["evaluation"]["highConfidenceOverride"] is False

    # Aggregate should reflect at least our 1 accepted example
    agg = result.dataset["analystAgent"]["aggregate"]
    assert agg["totalExamples"] >= 1
    assert agg["acceptedCount"] >= 1
    assert 0.0 <= agg["decisionAlignment"] <= 1.0


@pytest.mark.asyncio
async def test_export_flags_high_confidence_override() -> None:
    marker = f"EXPORT-OVERRIDE-{uuid4().hex[:8]}"
    order_id, _ = await _seed_analyst_sample(
        operator_decision=OperatorDecision.REJECTED,
        confidence=0.95,
        retailer_code=marker,
    )

    async with async_session_factory() as session:
        use_case = ExportDatasetUseCase(session=session, confidence_threshold=0.9)
        result = await use_case.execute(limit=500)

    examples = result.dataset["analystAgent"]["examples"]
    our = next(e for e in examples if e["orderId"] == order_id)
    assert our["evaluation"]["aligned"] is False
    assert our["evaluation"]["highConfidenceOverride"] is True


@pytest.mark.asyncio
async def test_export_marks_feedbacks_as_exported() -> None:
    marker = f"EXPORT-MARK-{uuid4().hex[:8]}"
    _, feedback_id = await _seed_analyst_sample(
        operator_decision=OperatorDecision.ACCEPTED,
        confidence=0.8,
        retailer_code=marker,
    )

    async with async_session_factory() as session:
        use_case = ExportDatasetUseCase(session=session)
        await use_case.execute(limit=500)

    async with async_session_factory() as session:
        feedback = (
            await session.execute(select(Feedback).where(Feedback.id == UUID(feedback_id)))
        ).scalar_one()
        assert feedback.phoenix_label_exported is True


@pytest.mark.asyncio
async def test_export_with_no_feedbacks_returns_empty_analyst_examples() -> None:
    """Use a very small limit on an already-populated DB to prove the shape
    degrades gracefully. (Cannot really assert "empty" because other tests
    pollute the DB; we at least assert the shape is valid.)"""
    async with async_session_factory() as session:
        use_case = ExportDatasetUseCase(session=session)
        result = await use_case.execute(limit=1)

    assert "analystAgent" in result.dataset
    assert "parserAgent" in result.dataset
    # Parser examples are intentionally empty (no correction flow yet)
    assert result.dataset["parserAgent"]["examples"] == []
    assert result.parser_examples_count == 0
