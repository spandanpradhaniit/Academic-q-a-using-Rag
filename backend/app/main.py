import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import analytics, auth, chat, conversations, documents, feedback, health, subjects
from app.core.rate_limit import enforce_rate_limit
from app.core.config import get_settings
from app.core.security_headers import SecurityHeadersMiddleware
from app.database.connection import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("academic_qa")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.faiss_dir.mkdir(parents=True, exist_ok=True)
    settings.bm25_dir.mkdir(parents=True, exist_ok=True)
    rate_limiter = None
    if settings.rate_limit_enabled:
        from redis.asyncio import Redis

        rate_limiter = Redis.from_url(settings.celery_broker_url, decode_responses=True)
        try:
            await rate_limiter.ping()
        except Exception:
            logger.exception("Redis rate limiter failed during startup")
            await rate_limiter.aclose()
            raise
    app.state.rate_limit_redis = rate_limiter
    from app.database.connection import Base
    import app.database.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("SQLAlchemy database engine initialized")
    try:
        yield
    finally:
        if rate_limiter is not None:
            await rate_limiter.aclose()
        engine.dispose()


app = FastAPI(
    title="Academic QA Hybrid RAG API",
    description="MySQL-backed academic document management and source-grounded hybrid RAG.",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_origin_regex=r"^https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)
app.middleware("http")(enforce_rate_limit)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error at %s", request.url.path)
    return JSONResponse(status_code=500, content={"success": False, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected server error occurred."}})


for router in (health.router, auth.router, subjects.router, documents.router, conversations.router, chat.router, feedback.router, analytics.router):
    app.include_router(router, prefix="/api")
