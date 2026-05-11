"""Integration tests for the API bootstrap surface."""


class TestApiBootstrap:
    """Test the versioned API scaffold."""

    def test_api_index_returns_discovery_metadata(self, client):
        """The versioned API root should advertise the current surface."""
        response = client.get("/api/v1")

        assert response.status_code == 200
        assert response.is_json
        assert response.get_json() == {
            "name": "meutch",
            "version": "v1",
            "status": "ok",
            "links": {
                "self": "/api/v1/",
                "health": "/api/v1/health",
            },
        }

    def test_api_health_returns_ok(self, client):
        """The health endpoint should respond without authentication."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.is_json
        assert response.get_json() == {
            "status": "ok",
            "version": "v1",
        }
