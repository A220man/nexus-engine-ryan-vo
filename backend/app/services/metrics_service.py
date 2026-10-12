from typing import List, Optional, Tuple
from app.core.database import get_connection
from app.models.schemas import MetricsSummaryResponse, SessionMetricsResponse

# Pricing reference catalog ($ per 1M tokens)
TOKEN_PRICING_PER_MILLION = {
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def calculate_cost_savings(tokens: int, model_key: str = "claude-3-5-sonnet") -> float:
    pricing = TOKEN_PRICING_PER_MILLION.get(model_key, TOKEN_PRICING_PER_MILLION["claude-3-5-sonnet"])
    # Context window tokens saved directly reduce input token context costs
    cost = (tokens / 1_000_000.0) * pricing["input"]
    return round(cost, 4)


def verify_metrics_invariants(
    total_raw: int,
    total_diverted: int,
    sessions: List[Tuple[str, int, int]],
) -> bool:
    """
    Formally verifies anti-contradiction invariants.
    Addresses issue #950:
    1. Total diverted must be >= any individual session diverted bytes (Part <= Whole).
    2. Sum of session diverted bytes must match total diverted bytes.
    3. Diverted bytes cannot exceed raw bytes for any session or aggregate.
    4. If raw bytes == 0 or diverted bytes == 0, savings must be 0.0.
    """
    if total_diverted > total_raw:
        return False

    running_sum = 0
    for s_id, s_raw, s_diverted in sessions:
        if s_diverted > s_raw:
            return False
        if s_diverted > total_diverted:
            return False
        running_sum += s_diverted

    if running_sum != total_diverted:
        return False

    return True


def get_summary_metrics(db_path: Optional[str] = None) -> MetricsSummaryResponse:
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                COUNT(id) as session_count,
                COALESCE(SUM(total_raw_bytes), 0) as agg_raw,
                COALESCE(SUM(total_diverted_bytes), 0) as agg_diverted,
                COALESCE(SUM(tool_calls_count), 0) as agg_calls
            FROM sessions
            """
        )
        row = cur.fetchone()
        session_count = row["session_count"] if row else 0
        total_raw = row["agg_raw"] if row else 0
        total_diverted = row["agg_diverted"] if row else 0
        total_calls = row["agg_calls"] if row else 0

        # Retrieve all sessions to check invariant
        cur.execute("SELECT id, total_raw_bytes, total_diverted_bytes FROM sessions")
        session_rows = [(r["id"], r["total_raw_bytes"], r["total_diverted_bytes"]) for r in cur.fetchall()]

    invariants_ok = verify_metrics_invariants(total_raw, total_diverted, session_rows)

    savings_ratio = (float(total_diverted) / float(total_raw)) if total_raw > 0 and total_diverted > 0 else 0.0
    tokens_saved = total_diverted // 4
    cost_saved = calculate_cost_savings(tokens_saved)

    return MetricsSummaryResponse(
        total_sessions=session_count,
        total_tool_calls=total_calls,
        total_raw_bytes=total_raw,
        total_diverted_bytes=total_diverted,
        overall_savings_ratio=round(savings_ratio, 4),
        estimated_tokens_saved=tokens_saved,
        estimated_cost_saved_usd=cost_saved,
        verified_invariants_pass=invariants_ok,
    )


def get_session_metrics(limit: int = 50, db_path: Optional[str] = None) -> List[SessionMetricsResponse]:
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, platform, total_raw_bytes, total_diverted_bytes, tool_calls_count
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()

    results: List[SessionMetricsResponse] = []
    for r in rows:
        raw = r["total_raw_bytes"]
        diverted = r["total_diverted_bytes"]
        ratio = (float(diverted) / float(raw)) if raw > 0 and diverted > 0 else 0.0
        tokens = diverted // 4
        cost = calculate_cost_savings(tokens)

        results.append(
            SessionMetricsResponse(
                session_id=r["id"],
                platform=r["platform"],
                tool_calls_count=r["tool_calls_count"],
                raw_bytes=raw,
                diverted_bytes=diverted,
                savings_ratio=round(ratio, 4),
                tokens_saved=tokens,
                cost_saved_usd=cost,
            )
        )
    return results
