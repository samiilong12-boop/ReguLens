"""System health check and diagnostic endpoints."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.api.deps import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic service liveness probe."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sectors_supported": ["AGRI_FOOD", "TEXTILES_APPAREL"],
    }


@router.get("/health/db", status_code=status.HTTP_200_OK)
async def database_health_check(db: AsyncSession = Depends(get_db)):
    """Database connectivity and readiness probe."""
    try:
        result = await db.execute(text("SELECT 1"))
        scalar = result.scalar()
        if scalar == 1:
            return {
                "status": "connected",
                "database": "postgresql",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return {"status": "unhealthy", "detail": "Unexpected query response"}
    except Exception as exc:
        return {
            "status": "disconnected",
            "detail": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
