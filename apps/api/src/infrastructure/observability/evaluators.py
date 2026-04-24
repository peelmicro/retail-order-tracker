"""Per-agent Phoenix-style evaluators.

Pure functions — no DB, no Phoenix SDK. The export use case calls them to
annotate each dataset example with quality metrics. Operators can then look
at `decisionAlignment` / `highConfidenceOverrides` in the exported JSON to
judge agent quality without opening Phoenix.

The Parser Agent evaluator is documented here but currently produces empty
datasets because we have no operator field-correction flow yet (see the
Phase 5 docs). When that flow exists, `parser_field_accuracy` will compare
the extracted OrderDTO against the corrected one.
"""

from dataclasses import dataclass

from src.domain.enums import OperatorDecision


@dataclass(frozen=True)
class ParserEvaluation:
    field_accuracy: float  # 0.0-1.0
    correction_count: int
    confidence_anomaly: bool  # high parsing_confidence but many corrections


@dataclass(frozen=True)
class AnalystEvaluation:
    aligned: bool  # operator agreed with the agent's action
    high_confidence_override: bool  # confidence above threshold but operator overrode


def parser_field_accuracy(
    extracted: dict,
    corrected: dict | None,
    *,
    parsing_confidence: float | None = None,
    correction_threshold: int = 2,
) -> ParserEvaluation:
    """Compare top-level fields of extracted vs corrected OrderDTO payloads.

    Returns `field_accuracy` = matching_fields / total_extracted_fields.
    `confidence_anomaly` flags cases where the agent self-reported high
    parsing_confidence (>0.8) but the operator had to correct more than
    `correction_threshold` fields.
    """
    if corrected is None or not corrected:
        # No operator corrections recorded = operator accepted the extraction.
        return ParserEvaluation(
            field_accuracy=1.0,
            correction_count=0,
            confidence_anomaly=False,
        )

    total = len(extracted)
    if total == 0:
        return ParserEvaluation(
            field_accuracy=0.0,
            correction_count=0,
            confidence_anomaly=False,
        )

    matching = sum(1 for k, v in extracted.items() if corrected.get(k) == v)
    accuracy = matching / total
    correction_count = total - matching
    confidence_anomaly = (
        parsing_confidence is not None
        and parsing_confidence > 0.8
        and correction_count > correction_threshold
    )
    return ParserEvaluation(
        field_accuracy=accuracy,
        correction_count=correction_count,
        confidence_anomaly=confidence_anomaly,
    )


def analyst_decision_alignment(
    *,
    suggestion_confidence: float,
    operator_decision: OperatorDecision,
    confidence_threshold: float = 0.9,
) -> AnalystEvaluation:
    """Evaluate whether the operator aligned with the agent's suggestion.

    - `aligned` = operator decision is ACCEPTED (operator approved of the agent).
    - `high_confidence_override` = agent's confidence exceeded `confidence_threshold`
       but the operator did NOT accept. High-confidence wrongness is the most
       important failure mode — surfaces prompt/model issues to investigate.
    """
    aligned = operator_decision == OperatorDecision.ACCEPTED
    high_confidence_override = (
        suggestion_confidence > confidence_threshold
        and operator_decision != OperatorDecision.ACCEPTED
    )
    return AnalystEvaluation(
        aligned=aligned,
        high_confidence_override=high_confidence_override,
    )
