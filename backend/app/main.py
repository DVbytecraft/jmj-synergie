"""
Biloz — FastAPI Application Entry Point
Clean Architecture | Version 1.0
"""
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine, Base
from app.middleware.logging import LoggingMiddleware
import app.infrastructure.database.models  # noqa: F401 — register all ORM models on Base.metadata
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = structlog.get_logger()

# ─── Sentry ───────────────────────────────────────────────────────────────────

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=settings.APP_VERSION,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        # Capturer 10 % des transactions en production pour les perf insights
        traces_sample_rate=0.1 if settings.is_production else 1.0,
        # Ne pas envoyer les 404 et 401 — trop de bruit
        before_send=lambda event, hint: (
            None
            if event.get("tags", {}).get("status_code") in (401, 404)
            else event
        ),
        send_default_pii=False,  # RGPD : pas d'IP ni d'email dans les events
    )
    logger.info("Sentry initialized", environment=settings.ENVIRONMENT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting Biloz API", version=settings.APP_VERSION)
    if settings.ENVIRONMENT == "testing":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("Shutting down Biloz API")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API de gestion des commandes Biloz",
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# ─── Prometheus metrics ───────────────────────────────────────────────────────

Instrumentator(
    should_group_status_codes=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# ─── Middleware (ordre important — dernier ajouté = premier exécuté) ──────────

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, calls=100, period=60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts_list,
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix="/api/v1")

# ─── Dev: expose unhandled 500 errors details to speed up debugging ────
# In production we keep a generic 500 to avoid leaking internals.
if settings.ENVIRONMENT != "production":
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc: Exception):
        logger.exception("unhandled.exception", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": exc.__class__.__name__},
        )



# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check():
    return JSONResponse({"status": "healthy", "version": settings.APP_VERSION})
