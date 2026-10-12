import os
import tempfile
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.database import init_db
from app.core.security import create_jwt_token
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def test_env():
    settings.ENVIRONMENT = "test"
    settings.DEMO_MODE = True
    settings.OIDC_ENABLED = False


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def client(temp_db: str) -> Generator[TestClient, None, None]:
    # Point settings to temp DB
    original_db = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite:///{temp_db}"
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    settings.DATABASE_URL = original_db


@pytest.fixture
def viewer_token() -> str:
    return create_jwt_token(
        payload={"sub": "viewer-user", "email": "viewer@example.com", "roles": ["viewer"]},
        secret_key=settings.JWT_SECRET_KEY,
    )


@pytest.fixture
def operator_token() -> str:
    return create_jwt_token(
        payload={"sub": "operator-user", "email": "operator@example.com", "roles": ["operator"]},
        secret_key=settings.JWT_SECRET_KEY,
    )


@pytest.fixture
def admin_token() -> str:
    return create_jwt_token(
        payload={"sub": "admin-user", "email": "admin@example.com", "roles": ["admin"]},
        secret_key=settings.JWT_SECRET_KEY,
    )
