import pytest
from app.services.metrics_service import (
    verify_metrics_invariants,
    calculate_cost_savings,
    get_summary_metrics,
    get_session_metrics,
)
from app.services.sandbox_service import store_sandbox_payload
from app.core.database import transaction


def test_metrics_invariants_pass():
    total_raw = 5000
    total_diverted = 4000
    sessions = [
        ("s1", 2500, 2000),
        ("s2", 2500, 2000),
    ]
    assert verify_metrics_invariants(total_raw, total_diverted, sessions) is True


def test_metrics_invariants_fail_part_greater_than_whole():
    # Issue #950: Part > Whole contradiction detection
    total_raw = 5000
    total_diverted = 1000  # Global total is 1000
    sessions = [
        ("s1", 4000, 3000),  # Session claims 3000 > 1000!
    ]
    assert verify_metrics_invariants(total_raw, total_diverted, sessions) is False


def test_zero_diverted_yields_zero_savings_not_100_percent(temp_db: str):
    # Issue #950: Session with zero output diversion must report strictly 0% savings
    with transaction(temp_db) as cur:
        cur.execute(
            """
            INSERT INTO sessions (id, platform, created_at, updated_at, total_raw_bytes, total_diverted_bytes, tool_calls_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("sess_zero", "claude-code", "2026-10-12T00:00:00Z", "2026-10-12T00:00:00Z", 0, 0, 0),
        )

    summary = get_summary_metrics(db_path=temp_db)
    assert summary.overall_savings_ratio == 0.0
    assert summary.estimated_tokens_saved == 0
    assert summary.estimated_cost_saved_usd == 0.0
    assert summary.verified_invariants_pass is True

    sessions = get_session_metrics(db_path=temp_db)
    assert len(sessions) == 1
    assert sessions[0].savings_ratio == 0.0


def test_session_metrics_breakdown(temp_db: str):
    content = "Line of log output with error diagnostics\n" * 150  # ~6300 bytes
    store_sandbox_payload(
        session_id="sess_active",
        command="build",
        raw_text=content,
        exit_code=0,
        db_path=temp_db,
    )
    summary = get_summary_metrics(db_path=temp_db)
    assert summary.total_sessions == 1
    assert summary.total_tool_calls == 1
    assert summary.total_raw_bytes > 0
    assert summary.total_diverted_bytes > 0
    assert summary.overall_savings_ratio > 0.5
    assert summary.verified_invariants_pass is True


def test_cost_savings_calculation():
    # 1,000,000 tokens on claude-3-5-sonnet at $3/M
    cost = calculate_cost_savings(1_000_000, model_key="claude-3-5-sonnet")
    assert cost == 3.0
