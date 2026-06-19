import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.database import create_tables
from app.logging_config import log_event, setup_logging
from app.routers import actions, auth, dashboard, drafts, extractions

setup_logging()
logger = logging.getLogger("app.main")

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event(logger, logging.INFO, "server_start",
              llm_mode="mock" if settings.use_mock_llm else "openai",
              model=settings.openai_model,
              database_url=settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url)
    create_tables()
    yield
    log_event(logger, logging.INFO, "server_stop")


app = FastAPI(
    title="SavePilot",
    description="Subscription & Refund Assistant MVP",
    version="0.2.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(extractions.router, prefix="/api")
app.include_router(actions.router, prefix="/api")
app.include_router(drafts.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    if request.url.path != "/api/health":
        log_event(logger, logging.INFO, "http_request",
                  method=request.method,
                  path=request.url.path,
                  status=response.status_code,
                  elapsed_ms=elapsed_ms,
                  client=request.client.host if request.client else "unknown")
    return response


@app.get("/api/health")
async def health_check():
    from sqlalchemy import text
    from app.database import engine

    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "llm_mode": "mock" if settings.use_mock_llm else "openai",
        "model": settings.openai_model,
    }
