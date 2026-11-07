"""Unit tests for the health check endpoints."""
import asyncio
from app.main import root_health
from app.api.v1.endpoints.health import health_check


def test_root_health_endpoint():
    data = asyncio.run(root_health())
    assert data["status"] == "healthy"
    assert "ReguLens" in data["service"]
    assert "AGRI_FOOD" in data["sectors_supported"]
    assert "TEXTILES_APPAREL" in data["sectors_supported"]


def test_api_v1_health_endpoint():
    data = asyncio.run(health_check())
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "sectors_supported" in data
