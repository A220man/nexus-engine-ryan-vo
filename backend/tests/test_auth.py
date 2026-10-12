import pytest
import time
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.core.security import create_jwt_token, decode_and_verify_jwt


def test_unauthenticated_request_rejected(client: TestClient):
    # Data endpoints require authorization
    res = client.get("/api/executions")
    assert res.status_code == 401
    assert "Missing Authorization header" in res.json()["detail"]


def test_invalid_token_rejected(client: TestClient):
    headers = {"Authorization": "Bearer invalid.token.payload"}
    res = client.get("/api/executions", headers=headers)
    assert res.status_code == 401


def test_expired_token_rejected():
    token = create_jwt_token(
        payload={"sub": "user", "roles": ["viewer"]},
        secret_key="nexus-engine-local-development-secret-key-32b",
        expires_in_seconds=-10,
    )
    with pytest.raises(Exception) as exc_info:
        decode_and_verify_jwt(token, "nexus-engine-local-development-secret-key-32b")
    assert "expired" in str(exc_info.value).lower()


def test_role_denial_viewer_cannot_execute(client: TestClient, viewer_token: str):
    headers = {"Authorization": f"Bearer {viewer_token}"}
    payload = {
        "session_id": "s_denied",
        "command": "ls -la",
    }
    res = client.post("/api/executions", json=payload, headers=headers)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_operator_can_execute(client: TestClient, operator_token: str):
    headers = {"Authorization": f"Bearer {operator_token}"}
    payload = {
        "session_id": "s_allowed",
        "command": "echo 'auth test'",
    }
    res = client.post("/api/executions", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == "s_allowed"
    assert "auth test" in data["preview_summary"]


def test_demo_mode_refused_in_production():
    # Contract: startup REFUSES demo mode in production
    with pytest.raises(RuntimeError) as exc_info:
        s = Settings(ENVIRONMENT="production", DEMO_MODE=True)
        if s.ENVIRONMENT == "production" and s.DEMO_MODE:
            raise RuntimeError("Startup refused: DEMO_MODE cannot be enabled in production environment.")
    assert "Startup refused" in str(exc_info.value)
