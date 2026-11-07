"""FastAPI main application entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.api.v1.router import api_router

# Initialize structured logging
setup_logging(log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_startup", service=settings.PROJECT_NAME, environment=settings.ENVIRONMENT)

    if settings.CHECK_DB_ROLE_ON_STARTUP:
        from app.db.session import async_session_maker, verify_database_role
        try:
            async with async_session_maker() as session:
                connected_role = await verify_database_role(session)
                logger.info("database_role_verified", role=connected_role)
        except Exception as exc:
            # If the database responded but violated security policy, fail immediately in all environments
            if isinstance(exc, RuntimeError) and "Security violation" in str(exc):
                logger.critical("database_security_violation", error=str(exc))
                raise

            # If the connection itself failed (e.g. database not reachable)
            env = (settings.ENVIRONMENT or "").strip().lower()
            if env in {"production", "prod", "staging"}:
                logger.critical("database_connection_failed_production", error=str(exc))
                raise RuntimeError("Production startup failed: Unable to connect to database to verify security boundaries.") from exc
            else:
                logger.warning(
                    "database_unreachable_startup",
                    warning="PostgreSQL is not reachable on startup. Database role verification was NOT RUN.",
                    environment=env,
                )

    yield
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS Middleware configuration
if settings.API_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.API_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Top-level health check endpoint
@app.get("/health", tags=["health"])
async def root_health():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "sectors_supported": ["AGRI_FOOD", "TEXTILES_APPAREL"],
    }
