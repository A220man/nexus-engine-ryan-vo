import pytest
from fastapi.testclient import TestClient


def test_healthcheck(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "nexus-engine"
    assert data["database"] == "connected"


def test_auth_demo_token(client: TestClient):
    res = client.post("/api/auth/demo-token", json={"role": "operator", "email": "op@test.com"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "operator"


def test_end_to_end_execution_search_and_metrics(client: TestClient, operator_token: str):
    headers = {"Authorization": f"Bearer {operator_token}"}

    # 1. Execute command producing substantial output
    cmd = "python3 -c \"for i in range(50): print(f'log line {i}: trace element matched')\""
    exec_res = client.post(
        "/api/executions",
        json={"session_id": "sess_integration", "command": cmd, "platform": "claude-code"},
        headers=headers,
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    execution_id = exec_data["id"]
    assert exec_data["is_sandboxed"] is True
    assert exec_data["chunks_count"] >= 1

    # 2. Retrieve execution detail
    detail_res = client.get(f"/api/executions/{execution_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == execution_id

    # 3. Retrieve chunks
    chunks_res = client.get(f"/api/executions/{execution_id}/chunks", headers=headers)
    assert chunks_res.status_code == 200
    assert len(chunks_res.json()) >= 1

    # 4. Search within sandbox
    search_res = client.get(
        f"/api/sandboxes/{execution_id}/search",
        params={"query": "log line 25"},
        headers=headers,
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_matches"] == 1
    assert "log line 25" in search_data["results"][0]["snippet"]

    # 5. Check metrics summary
    metrics_res = client.get("/api/metrics/summary", headers=headers)
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert metrics_data["total_sessions"] >= 1
    assert metrics_data["total_tool_calls"] >= 1
    assert metrics_data["verified_invariants_pass"] is True

    # 6. Check session metrics
    sessions_res = client.get("/api/metrics/sessions", headers=headers)
    assert sessions_res.status_code == 200
    sessions_data = sessions_res.json()
    assert any(s["session_id"] == "sess_integration" for s in sessions_data)


def test_platforms_list_and_config(client: TestClient, viewer_token: str):
    headers = {"Authorization": f"Bearer {viewer_token}"}
    res = client.get("/api/platforms", headers=headers)
    assert res.status_code == 200
    platforms = res.json()
    assert len(platforms) == 17

    cfg_res = client.get("/api/platforms/opencode-v2/config", headers=headers)
    assert cfg_res.status_code == 200
    cfg_data = cfg_res.json()
    assert "opencode" in cfg_data["config_snippet"]


def test_evaluation_endpoint(client: TestClient, operator_token: str):
    headers = {"Authorization": f"Bearer {operator_token}"}
    res = client.post("/api/evaluation/run", json={"max_samples": 5}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_samples"] >= 1
    assert data["compression_ratio"] > 0
    assert data["classifier_safety_score"] == 100.0
