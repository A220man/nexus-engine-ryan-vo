from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api.endpoints import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite schema and tables on startup
    init_db()
    yield


def create_app() -> FastAPI:
    """
    Factory creating and configuring the Nexus Engine FastAPI application.
    Docker container and local Uvicorn commands use this identical entrypoint.
    """
    app = FastAPI(
        title="Nexus Engine",
        description="Context window optimization engine for AI coding agents",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration allowing local developer frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.get("/")
    def root():
        return {
            "name": "Nexus Engine",
            "version": "1.0.0",
            "description": "Context window optimization engine for AI coding agents",
            "docs_url": "/docs",
            "api_url": "/api",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
