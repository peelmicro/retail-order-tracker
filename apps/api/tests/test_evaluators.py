"""Pure-function tests for the per-agent evaluators."""

import pytest

from src.domain.enums import OperatorDecision
from src.infrastructure.observability.evaluators import (
    analyst_decision_alignment,
    parser_field_accuracy,
)


# ---- Parser evaluator ----------------------------------------------------


def test_parser_no_corrections_means_full_accuracy() -> None:
    result = parser_field_accuracy(
        extracted={"orderNumber": "PO-1", "currencyCode": "EUR"},
        corrected=None,
    )
    assert result.field_accuracy == 1.0
    assert result.correction_count == 0
    assert result.confidence_anomaly is False


def test_parser_partial_match() -> None:
    result = parser_field_accuracy(
        extracted={"orderNumber": "PO-1", "currencyCode": "USD", "supplierCode": "X"},
        corrected={"orderNumber": "PO-1", "currencyCode": "EUR", "supplierCode": "X"},
    )
    assert result.field_accuracy == pytest.approx(2 / 3)
    assert result.correction_count == 1


def test_parser_high_confidence_anomaly_flagged() -> None:
    """Agent reported confidence 0.95 but operator corrected 3 fields → anomaly."""
    result = parser_field_accuracy(
        extracted={"a": 1, "b": 2, "c": 3, "d": 4},
        corrected={"a": 99, "b": 99, "c": 99, "d": 4},  # 3 corrections
        parsing_confidence=0.95,
    )
    assert result.correction_count == 3
    assert result.confidence_anomaly is True


def test_parser_low_confidence_correction_not_flagged() -> None:
    """Low confidence + corrections is expected — not an anomaly."""
    result = parser_field_accuracy(
        extracted={"a": 1, "b": 2, "c": 3},
        corrected={"a": 99, "b": 99, "c": 99},
        parsing_confidence=0.5,
    )
    assert result.confidence_anomaly is False


def test_parser_empty_extracted_edge_case() -> None:
    result = parser_field_accuracy(extracted={}, corrected={"x": 1})
    assert result.field_accuracy == 0.0


# ---- Analyst evaluator ---------------------------------------------------


def test_analyst_accepted_is_aligned() -> None:
    result = analyst_decision_alignment(
        suggestion_confidence=0.95,
        operator_decision=OperatorDecision.ACCEPTED,
    )
    assert result.aligned is True
    assert result.high_confidence_override is False


def test_analyst_high_confidence_but_rejected_is_override() -> None:
    result = analyst_decision_alignment(
        suggestion_confidence=0.95,
        operator_decision=OperatorDecision.REJECTED,
    )
    assert result.aligned is False
    assert result.high_confidence_override is True


def test_analyst_high_confidence_modified_is_also_override() -> None:
    result = analyst_decision_alignment(
        suggestion_confidence=0.95,
        operator_decision=OperatorDecision.MODIFIED,
    )
    assert result.aligned is False
    assert result.high_confidence_override is True


def test_analyst_low_confidence_rejection_is_not_override() -> None:
    result = analyst_decision_alignment(
        suggestion_confidence=0.5,
        operator_decision=OperatorDecision.REJECTED,
    )
    assert result.aligned is False
    assert result.high_confidence_override is False


def test_analyst_threshold_is_strict_greater_than() -> None:
    """Confidence exactly at threshold is NOT flagged (strict greater-than)."""
    result = analyst_decision_alignment(
        suggestion_confidence=0.9,
        operator_decision=OperatorDecision.REJECTED,
        confidence_threshold=0.9,
    )
    assert result.high_confidence_override is False
