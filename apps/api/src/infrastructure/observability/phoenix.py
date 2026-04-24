"""Phoenix OTLP tracer bootstrap.

Registers an OpenTelemetry tracer provider pointed at the self-hosted Phoenix
collector (see docker-compose.infra.yml) and instruments LangChain so every
agent invocation emits spans with OpenInference semantic conventions. The
Phoenix UI at http://localhost:6006 renders them as nested agent steps.

Import-safe: if Phoenix is unreachable or optional deps are missing, we log a
warning and continue. This keeps the app usable in environments without AI
(e.g. tests that don't touch agents).
"""

from __future__ import annotations

import logging

from src.config import settings

_log = logging.getLogger(__name__)

_initialized = False


def init_phoenix(service_name: str = "retail-order-tracker") -> None:
    """Idempotent Phoenix + LangChain instrumentation setup.

    Safe to call multiple times (re-calls become no-ops).
    """
    global _initialized
    if _initialized:
        return

    if not settings.phoenix_endpoint:
        _log.info("Phoenix endpoint not configured — tracing disabled")
        _initialized = True
        return

    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        tracer_provider = register(
            project_name=service_name,
            endpoint=f"{settings.phoenix_endpoint.rstrip('/')}/v1/traces",
            auto_instrument=False,
            set_global_tracer_provider=True,
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        _log.info(
            "Phoenix tracing initialized — service=%s endpoint=%s",
            service_name,
            settings.phoenix_endpoint,
        )
    except Exception as exc:  # noqa: BLE001 — observability must never fail the app
        _log.warning("Phoenix init failed (traces will not be exported): %s", exc)

    _initialized = True
