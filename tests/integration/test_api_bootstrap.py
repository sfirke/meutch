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
            "api_enabled": True,
            "write_enabled": True,
        }

    def test_api_health_assigns_request_id_header(self, client):
        """API responses should expose a stable request id for log correlation."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.headers["X-Request-ID"]

    def test_api_health_preserves_incoming_request_id_header(self, client):
        """When a caller supplies a request id, the API should echo it back."""
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "trace-123"},
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "trace-123"

    def test_disabled_api_returns_503_for_non_health_routes(self, client, app):
        """The rollout kill switch should block normal API traffic while keeping health up."""
        original_enabled = app.config["API_V1_ENABLED"]

        try:
            app.config["API_V1_ENABLED"] = False

            response = client.get("/api/v1")
            health_response = client.get("/api/v1/health")

            assert response.status_code == 503
            assert response.get_json() == {
                "error": {
                    "code": "API_DISABLED",
                    "message": "The API is temporarily unavailable.",
                    "details": {},
                }
            }
            assert health_response.status_code == 200
            assert health_response.get_json() == {
                "status": "disabled",
                "version": "v1",
                "api_enabled": False,
                "write_enabled": True,
            }
        finally:
            app.config["API_V1_ENABLED"] = original_enabled

    def test_read_only_rollout_blocks_mutations_but_allows_auth_writes(self, client, app):
        """Read-only mode should preserve auth/session routes while blocking member mutations."""
        original_write_enabled = app.config["API_V1_WRITE_ENABLED"]

        try:
            app.config["API_V1_WRITE_ENABLED"] = False

            blocked_response = client.patch("/api/v1/me/profile", json={"about_me": "ignored"})
            auth_response = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "missing@example.com"},
            )

            assert blocked_response.status_code == 503
            assert blocked_response.get_json() == {
                "error": {
                    "code": "API_READ_ONLY",
                    "message": "The API is temporarily in read-only mode.",
                    "details": {},
                }
            }
            assert auth_response.status_code == 200
            assert auth_response.get_json() == {
                "message": "If an account with that email exists, password reset instructions have been sent."
            }
        finally:
            app.config["API_V1_WRITE_ENABLED"] = original_write_enabled
