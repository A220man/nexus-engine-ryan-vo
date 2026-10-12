from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.core.config import settings
from app.core.database import get_connection, log_audit
from app.core.security import get_current_user, require_role, create_jwt_token, UserContext
from app.models.schemas import (
    ExecutionCreateRequest,
    ExecutionResponse,
    ChunkResponse,
    SandboxCreateRequest,
    SandboxSearchRequest,
    SandboxSearchResponse,
    MetricsSummaryResponse,
    SessionMetricsResponse,
    PlatformConfigResponse,
    EvaluationRunRequest,
    EvaluationResultResponse,
    AdvisoryExplainRequest,
    AdvisoryExplainResponse,
)
from app.services.sandbox_service import (
    store_sandbox_payload,
    get_execution,
    get_chunks_for_execution,
    search_in_sandbox,
)
from app.services.executor_service import run_bounded_command, abort_execution
from app.services.metrics_service import get_summary_metrics, get_session_metrics
from app.services.routing_service import list_supported_platforms, generate_platform_config
from app.services.llm_service import generate_advisory_explanation
from app.evaluation import run_evaluation

router = APIRouter()


class DemoTokenRequest(BaseModel):
    role: str = "operator"
    email: str = "demo@example.com"


class DemoTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str
    expires_in: int


@router.get("/health")
def health_check() -> Dict[str, Any]:
    # Check DB connectivity
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy",
        "service": "nexus-engine",
        "database": db_status,
        "demo_mode": settings.DEMO_MODE,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/auth/config")
def auth_config() -> Dict[str, Any]:
    return {
        "oidc_enabled": settings.OIDC_ENABLED,
        "oidc_issuer_url": settings.OIDC_ISSUER_URL,
        "oidc_client_id": settings.OIDC_CLIENT_ID,
        "oidc_audience": settings.OIDC_AUDIENCE,
        "demo_mode": settings.DEMO_MODE,
        "environment": settings.ENVIRONMENT,
        "roles": ["viewer", "operator", "admin"],
    }


@router.post("/auth/demo-token", response_model=DemoTokenResponse)
def get_demo_token(req: DemoTokenRequest) -> DemoTokenResponse:
    if not settings.DEMO_MODE or settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo token endpoint is strictly disabled in production or when DEMO_MODE is false.",
        )
    role = req.role if req.role in {"viewer", "operator", "admin"} else "viewer"
    token = create_jwt_token(
        payload={"sub": "demo-user", "email": req.email, "roles": [role]},
        secret_key=settings.JWT_SECRET_KEY,
        expires_in_seconds=7200,
    )
    return DemoTokenResponse(
        access_token=token,
        role=role,
        email=req.email,
        expires_in=7200,
    )


@router.post("/executions", response_model=ExecutionResponse)
def execute_command(
    req: ExecutionCreateRequest,
    user: UserContext = Depends(require_role(["operator", "admin"])),
) -> ExecutionResponse:
    try:
        record = run_bounded_command(
            command=req.command,
            timeout_seconds=req.timeout_seconds,
            session_id=req.session_id,
            platform=req.platform,
            cwd=req.working_directory,
        )
        log_audit(
            user_sub=user.sub,
            user_role=",".join(user.roles),
            action="execute_command",
            resource=record.id,
            details={"command": req.command, "session_id": req.session_id},
        )
        return record
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/executions", response_model=List[ExecutionResponse])
def list_executions(
    session_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(require_role(["viewer", "operator", "admin"])),
) -> List[ExecutionResponse]:
    with get_connection() as conn:
        cur = conn.cursor()
        if session_id:
            cur.execute(
                """
                SELECT e.*, COUNT(c.id) as chunks_count
                FROM executions e
                LEFT JOIN output_chunks c ON c.execution_id = e.id
                WHERE e.session_id = ?
                GROUP BY e.id
                ORDER BY e.created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT e.*, COUNT(c.id) as chunks_count
                FROM executions e
                LEFT JOIN output_chunks c ON c.execution_id = e.id
                GROUP BY e.id
                ORDER BY e.created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cur.fetchall()

    return [
        ExecutionResponse(
            id=r["id"],
            session_id=r["session_id"],
            command=r["command"],
            status=r["status"],
            exit_code=r["exit_code"],
            duration_ms=r["duration_ms"],
            raw_bytes=r["raw_bytes"],
            sandboxed_bytes=r["sandboxed_bytes"],
            is_sandboxed=bool(r["is_sandboxed"]),
            preview_summary=r["preview_summary"],
            created_at=r["created_at"],
            chunks_count=r["chunks_count"],
        )
        for r in rows
    ]


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
def get_execution_detail(
    execution_id: str,
    user: UserContext = Depends(require_role(["viewer", "operator", "admin"])),
) -> ExecutionResponse:
    record = get_execution(execution_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return record


@router.get("/executions/{execution_id}/chunks", response_model=List[ChunkResponse])
def get_execution_chunks(
    execution_id: str,
    user: UserContext = Depends(require_role(["viewer", "operator", "admin"])),
) -> List[ChunkResponse]:
    return get_chunks_for_execution(execution_id)


@router.post("/executions/{execution_id}/abort")
def abort_running_execution(
    execution_id: str,
    user: UserContext = Depends(require_role(["operator", "admin"])),
) -> Dict[str, Any]:
    success = abort_execution(execution_id)
    log_audit(
        user_sub=user.sub,
        user_role=",".join(user.roles),
        action="abort_execution",
        resource=execution_id,
        details={"aborted": success},
    )
    return {"execution_id": execution_id, "aborted": success}


@router.post("/sandboxes", response_model=ExecutionResponse)
def create_sandbox_payload(
    req: SandboxCreateRequest,
    user: UserContext = Depends(require_role(["operator", "admin"])),
) -> ExecutionResponse:
    record = store_sandbox_payload(
        session_id=req.session_id,
        command=req.title or "direct_sandbox_store",
        raw_text=req.text,
        exit_code=0,
        platform=req.platform,
    )
    log_audit(
        user_sub=user.sub,
        user_role=",".join(user.roles),
        action="create_sandbox",
        resource=record.id,
        details={"session_id": req.session_id, "raw_bytes": record.raw_bytes},
    )
    return record


@router.get("/sandboxes/{execution_id}/search", response_model=SandboxSearchResponse)
def search_sandbox(
    execution_id: str,
    query: str = Query(..., min_length=1),
    regex: bool = Query(False),
    max_results: int = Query(10, ge=1, le=100),
    user: UserContext = Depends(require_role(["viewer", "operator", "admin"])),
) -> SandboxSearchResponse:
    record = get_execution(execution_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox artifact not found")
    return search_in_sandbox(
        execution_id=execution_id,
        query=query,
        regex=regex,
        max_results=max_results,
    )


@router.get("/metrics/summary", response_model=MetricsSummaryResponse)
def get_metrics_summary(
    user: UserContext = Depends(require_role(["viewer", "operator", "admin"])),
) -> MetricsSummaryResponse:
    return get_summary_metrics()


@router.get("/metrics/sessions", response_model=List[SessionMetricsResponse])
def get_metrics_sessions(
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(require_role(["viewer", "operator", "admin"])),
) -> List[SessionMetricsResponse]:
    return get_session_metrics(limit=limit)


@router.get("/platforms", response_model=List[PlatformConfigResponse])
def get_platforms(
    user: UserContext = Depends(require_role(["viewer", "operator", "admin"])),
) -> List[PlatformConfigResponse]:
    return list_supported_platforms()


@router.get("/platforms/{platform_id}/config", response_model=PlatformConfigResponse)
def get_platform_configuration(
    platform_id: str,
    quiet_mode: bool = Query(False),
    user: UserContext = Depends(require_role(["viewer", "operator", "admin"])),
) -> PlatformConfigResponse:
    return generate_platform_config(platform_id=platform_id, quiet_mode=quiet_mode)


@router.post("/evaluation/run", response_model=EvaluationResultResponse)
def trigger_evaluation(
    req: EvaluationRunRequest,
    user: UserContext = Depends(require_role(["operator", "admin"])),
) -> EvaluationResultResponse:
    res = run_evaluation(dataset_path=req.dataset_path, max_samples=req.max_samples)
    log_audit(
        user_sub=user.sub,
        user_role=",".join(user.roles),
        action="run_evaluation",
        resource="evaluation_suite",
        details={"samples": res.total_samples, "compression": res.compression_ratio},
    )
    return res


@router.post("/advisory/explain", response_model=AdvisoryExplainResponse)
async def explain_execution(
    req: AdvisoryExplainRequest,
    user: UserContext = Depends(require_role(["operator", "admin"])),
) -> AdvisoryExplainResponse:
    record = get_execution(req.execution_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution artifact not found")
    try:
        res = await generate_advisory_explanation(execution=record, prompt_hint=req.prompt_hint)
        log_audit(
            user_sub=user.sub,
            user_role=",".join(user.roles),
            action="explain_advisory",
            resource=req.execution_id,
            details={"provider": res.provider},
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
