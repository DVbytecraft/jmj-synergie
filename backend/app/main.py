"""
JMJ Synergie — FastAPI Application Entry Point
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

from fastapi import Request

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis_client import close_redis
from app.middleware.logging import LoggingMiddleware
from app.middleware.metrics_auth import MetricsAuthMiddleware
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
            if (
                event.get("level") == "warning"
                and event.get("extra", {}).get("status_code") in (401, 403, 404)
            )
            or (
                hint
                and isinstance(hint.get("exc_info", (None,))[1], Exception)
                and getattr(hint["exc_info"][1], "status_code", None) in (401, 403, 404)
            )
            else event
        ),
        send_default_pii=False,  # RGPD : pas d'IP ni d'email dans les events
    )
    logger.info("Sentry initialized", environment=settings.ENVIRONMENT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting JMJ Synergie API", version=settings.APP_VERSION)
    if settings.is_production and not settings.USE_CLOUDINARY:
        logger.warning(
            "storage.local_in_production",
            message=(
                "USE_CLOUDINARY=False en production — les fichiers sont stockés localement "
                "et seront perdus à chaque redéploiement. Activez Cloudinary."
            ),
        )
    if settings.ENVIRONMENT == "testing":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("Shutting down JMJ Synergie API")
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API de gestion des commandes JMJ Synergie",
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
app.add_middleware(MetricsAuthMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, calls=100, period=60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Idempotency-Key"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts_list,
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix="/api/v1")

# ─── Global domain exception handlers ─────────────────────────────────────────

from sqlalchemy.exc import IntegrityError as SAIntegrityError, ProgrammingError as SAProgrammingError, OperationalError as SAOperationalError

from app.core.exceptions import (
    AppException,
    EntityNotFoundError,
    DuplicateEntityError,
    PermissionDeniedError,
    BusinessRuleError,
)


@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundError):
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(DuplicateEntityError)
async def duplicate_entity_handler(request: Request, exc: DuplicateEntityError):
    return JSONResponse(status_code=409, content={"detail": exc.message})


@app.exception_handler(PermissionDeniedError)
async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
    return JSONResponse(status_code=403, content={"detail": exc.message})


@app.exception_handler(BusinessRuleError)
async def business_rule_handler(request: Request, exc: BusinessRuleError):
    logger.warning("domain.business_rule", path=request.url.path, detail=exc.message)
    return JSONResponse(status_code=422, content={"detail": exc.message})


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.warning("domain.app_error", path=request.url.path, code=exc.code, detail=exc.message)
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning("domain.value_error", path=request.url.path, detail=str(exc))
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    logger.warning("domain.permission_error", path=request.url.path, detail=str(exc))
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(SAIntegrityError)
async def integrity_error_handler(request: Request, exc: SAIntegrityError):
    logger.warning("db.integrity_error", path=request.url.path, detail=str(exc.orig))
    orig = str(exc.orig or "")
    if "unique" in orig.lower() or "duplicate" in orig.lower():
        return JSONResponse(status_code=409, content={"detail": "Cette valeur existe déjà. Vérifiez les champs uniques."})
    return JSONResponse(status_code=400, content={"detail": "Erreur de contrainte en base de données."})


@app.exception_handler(SAProgrammingError)
async def programming_error_handler(request: Request, exc: SAProgrammingError):
    logger.error("db.programming_error", path=request.url.path, detail=str(exc.orig or exc))
    return JSONResponse(status_code=500, content={"detail": "Erreur de schéma base de données. Contactez le support."})


@app.exception_handler(SAOperationalError)
async def operational_error_handler(request: Request, exc: SAOperationalError):
    logger.error("db.operational_error", path=request.url.path, detail=str(exc.orig or exc))
    return JSONResponse(status_code=503, content={"detail": "Base de données temporairement indisponible."})


# ─── Dev: expose unhandled 500 error details to speed up debugging ─────────────
if settings.ENVIRONMENT != "production":
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled.exception", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": exc.__class__.__name__},
        )


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check():
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "degraded"
    body: dict = {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "db": db_status,
    }
    if not settings.is_production:
        body["version"] = settings.APP_VERSION
    return JSONResponse(body)
