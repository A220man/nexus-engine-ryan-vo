from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ExecutionCreateRequest(BaseModel):
    session_id: str = Field(..., description="Unique conversation session identifier")
    command: str = Field(..., description="Shell command or tool operation to execute")
    platform: str = Field(default="generic", description="Target agent platform (e.g. claude-code, codex)")
    timeout_seconds: Optional[int] = Field(default=None, description="Execution watchdog timeout in seconds")
    working_directory: Optional[str] = Field(default=None, description="Optional working directory")


class ExecutionResponse(BaseModel):
    id: str
    session_id: str
    command: str
    status: str
    exit_code: Optional[int] = None
    duration_ms: float
    raw_bytes: int
    sandboxed_bytes: int
    is_sandboxed: bool
    preview_summary: str
    created_at: str
    chunks_count: int


class ChunkResponse(BaseModel):
    id: str
    chunk_index: int
    byte_length: int
    content: str
    checksum: str
    created_at: str


class SandboxCreateRequest(BaseModel):
    session_id: str
    text: str
    platform: str = "generic"
    title: Optional[str] = None


class SandboxSearchRequest(BaseModel):
    query: str
    regex: bool = False
    max_results: int = 10


class SearchResultItem(BaseModel):
    chunk_index: int
    line_number: int
    snippet: str
    match_score: float


class SandboxSearchResponse(BaseModel):
    execution_id: str
    total_matches: int
    results: List[SearchResultItem]


class MetricsSummaryResponse(BaseModel):
    total_sessions: int
    total_tool_calls: int
    total_raw_bytes: int
    total_diverted_bytes: int
    overall_savings_ratio: float
    estimated_tokens_saved: int
    estimated_cost_saved_usd: float
    verified_invariants_pass: bool


class SessionMetricsResponse(BaseModel):
    session_id: str
    platform: str
    tool_calls_count: int
    raw_bytes: int
    diverted_bytes: int
    savings_ratio: float
    tokens_saved: int
    cost_saved_usd: float


class PlatformConfigResponse(BaseModel):
    platform_id: str
    name: str
    category: str
    hook_mode: str
    config_snippet: str
    tool_guidance_block: str
    quiet_mode_supported: bool
    version_supported: str


class EvaluationRunRequest(BaseModel):
    dataset_path: Optional[str] = None
    max_samples: int = 50


class EvaluationResultResponse(BaseModel):
    total_samples: int
    average_raw_bytes: float
    average_sandboxed_bytes: float
    compression_ratio: float
    retrieval_recall: float
    classifier_safety_score: float
    run_duration_ms: float
    provenance: str


class AdvisoryExplainRequest(BaseModel):
    execution_id: str
    prompt_hint: Optional[str] = None


class AdvisoryExplainResponse(BaseModel):
    execution_id: str
    provider: str
    model: str
    explanation: str
    advisory_notice: str
    latency_ms: float
