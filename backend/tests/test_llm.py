import asyncio
import pytest
import httpx
from app.core.config import settings
from app.models.schemas import ExecutionResponse
from app.services.llm_service import (
    generate_advisory_explanation,
    redact_sensitive_strings,
    LLMProviderError,
)


def test_offline_fallback_without_key():
    settings.LLM_API_KEY = ""
    dummy_exec = ExecutionResponse(
        id="exec_test_offline",
        session_id="sess_offline",
        command="npm run build",
        status="completed",
        exit_code=1,
        duration_ms=120.0,
        raw_bytes=1024,
        sandboxed_bytes=256,
        is_sandboxed=True,
        preview_summary="Error: failed to build",
        created_at="2026-10-12T00:00:00Z",
        chunks_count=1,
    )
    res = asyncio.run(generate_advisory_explanation(execution=dummy_exec))
    assert res.provider == "offline-deterministic"
    assert res.model == "built-in-heuristics"
    assert "Offline Advisory Mode" in res.explanation
    assert "ADVISORY ONLY" in res.advisory_notice


def test_redact_sensitive_strings_runtime_synthetic():
    # Security rule: never paste token-shaped credential literals.
    # Generate purely synthetic test value at runtime.
    synthetic_key = "sk-" + "0" * 32
    raw_error = f"Connection error when communicating with key {synthetic_key} on endpoint"
    cleaned = redact_sensitive_strings(raw_error)
    assert synthetic_key not in cleaned
    assert "[REDACTED_SECRET]" in cleaned
