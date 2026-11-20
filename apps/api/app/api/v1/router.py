"""API v1 root router."""
from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, documents

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
