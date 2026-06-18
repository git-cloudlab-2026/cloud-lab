from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import ApiError, api_error_handler, unhandled_error_handler


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime()
    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        description="Backend FastAPI + PostgreSQL pour Cloud Lab Control Center.",
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        https_only=settings.environment == "production",
        same_site="lax",
    )
    app.include_router(api_router)

    frontend_dir = Path("/app/frontend")
    if frontend_dir.exists():
        app.mount("/portal", StaticFiles(directory=frontend_dir, html=True), name="portal")

        @app.get("/")
        async def portal_home():
            return FileResponse(frontend_dir / "index.html")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "cloud-lab-fastapi"}

    return app


app = create_app()
