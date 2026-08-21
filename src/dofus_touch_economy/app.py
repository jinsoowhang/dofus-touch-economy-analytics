from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from dofus_touch_economy.config import Settings
from dofus_touch_economy.database import create_engine_for_url, create_session_factory

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        yield session


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def create_app(
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    from dofus_touch_economy.routers import api, web

    resolved_settings = settings or Settings.from_env()
    owned_engine: Engine | None = None
    if session_factory is None:
        owned_engine = create_engine_for_url(resolved_settings.database_url)
        session_factory = create_session_factory(owned_engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_engine is not None:
            owned_engine.dispose()

    application = FastAPI(title="Dofus Touch Economy", lifespan=lifespan)
    application.state.settings = resolved_settings
    application.state.session_factory = session_factory

    @application.middleware("http")
    async def enforce_same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in UNSAFE_METHODS and origin is not None:
            origin_authority = urlsplit(origin).netloc.casefold()
            request_authority = request.headers.get("host", "").casefold()
            if not origin_authority or origin_authority != request_authority:
                return JSONResponse(
                    status_code=403, content={"detail": "cross-origin request denied"}
                )
        return await call_next(request)

    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(resolved_settings.allowed_hosts),
    )
    static_directory = Path(__file__).resolve().parent / "static"
    application.mount(
        "/static",
        StaticFiles(directory=static_directory, check_dir=False),
        name="static",
    )
    application.include_router(web.router)
    application.include_router(api.router, prefix="/api/v1")
    return application
