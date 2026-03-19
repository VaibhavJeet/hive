"""
Tests for API health and basic endpoints.

These tests verify the API is correctly structured and responds appropriately.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check_structure(self):
        """Test that health check returns expected structure."""
        # Import here to avoid import errors during collection
        from mind.api.main import app

        with TestClient(app) as client:
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_detailed_health_check_structure(self):
        """Test that detailed health check returns component statuses."""
        from mind.api.main import app

        with TestClient(app) as client:
            response = client.get("/health/detailed")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            # Should have components section
            if "components" in data:
                assert isinstance(data["components"], dict)


class TestOpenAPISpec:
    """Test that OpenAPI spec is correctly generated."""

    def test_openapi_spec_exists(self):
        """Test that OpenAPI spec endpoint works."""
        from mind.api.main import app

        with TestClient(app) as client:
            response = client.get("/openapi.json")

            assert response.status_code == 200
            data = response.json()
            assert "openapi" in data
            assert "paths" in data
            assert "info" in data

    def test_docs_endpoint(self):
        """Test that docs endpoint redirects or serves content."""
        from mind.api.main import app

        with TestClient(app) as client:
            response = client.get("/docs")

            # Should either return docs or redirect
            assert response.status_code in [200, 307, 308]


class TestCORSConfiguration:
    """Test CORS is configured correctly."""

    def test_cors_headers_on_options(self):
        """Test that CORS preflight requests work."""
        from mind.api.main import app

        with TestClient(app) as client:
            response = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                }
            )

            # Should allow CORS
            assert response.status_code in [200, 204]


class TestAPIMetadata:
    """Test API metadata and versioning."""

    def test_api_title(self):
        """Test that API has correct title."""
        from mind.api.main import app

        assert app.title is not None
        assert len(app.title) > 0

    def test_api_version(self):
        """Test that API has version defined."""
        from mind.api.main import app

        assert app.version is not None
