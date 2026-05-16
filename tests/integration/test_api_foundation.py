"""Integration tests for shared API error and response helpers."""

import pytest
from flask import request
from marshmallow import ValidationError

from app.api.v1 import bp as api_v1_bp
from app.api.v1.responses import build_collection_response
from app.services.exceptions import (
    AuthorizationError,
    ConflictError,
    InformationalError,
    InvalidActionError,
)
from app.utils.pagination import ListPagination


@api_v1_bp.get("/__tests__/service-error")
def api_test_service_error():
    """Raise a service exception to verify API error translation."""
    kind = request.args["kind"]

    if kind == "authorization":
        raise AuthorizationError("You cannot view this resource.")
    if kind == "conflict":
        raise ConflictError("This item is not currently available to borrow.")
    if kind == "informational":
        raise InformationalError("This request is missing required state.")
    if kind == "invalid_action":
        raise InvalidActionError("This transition is not allowed.")

    raise AssertionError(f"Unexpected service error kind: {kind}")


@api_v1_bp.get("/__tests__/validation-error")
def api_test_validation_error():
    """Raise a Marshmallow ValidationError to verify 422 translation."""
    raise ValidationError({"name": ["Missing data for required field."]})


@api_v1_bp.get("/__tests__/paginated")
def api_test_paginated_response():
    """Return a paginated payload using the shared API response helper."""
    items = [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"},
        {"id": 3, "name": "Item 3"},
        {"id": 4, "name": "Item 4"},
        {"id": 5, "name": "Item 5"},
    ]
    pagination = ListPagination(items=items, page=2, per_page=2)
    return build_collection_response("items", pagination.items, pagination=pagination)


class TestApiFoundation:
    """Test API-wide error mapping and response helpers."""

    def test_missing_api_route_returns_json_404(self, client):
        """Unknown API routes should return a structured JSON error."""
        response = client.get("/api/v1/missing")

        assert response.status_code == 404
        assert response.is_json
        assert response.get_json() == {
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource was not found.",
                "details": {},
            }
        }

    @pytest.mark.parametrize(
        ("kind", "status_code", "code", "message"),
        [
            (
                "authorization",
                403,
                "FORBIDDEN",
                "You cannot view this resource.",
            ),
            (
                "conflict",
                409,
                "CONFLICT",
                "This item is not currently available to borrow.",
            ),
            (
                "informational",
                400,
                "BAD_REQUEST",
                "This request is missing required state.",
            ),
            (
                "invalid_action",
                400,
                "INVALID_ACTION",
                "This transition is not allowed.",
            ),
        ],
    )
    def test_service_errors_map_to_standard_api_responses(
        self, client, kind, status_code, code, message
    ):
        """Service-layer failures should map to stable status and error codes."""
        response = client.get(f"/api/v1/__tests__/service-error?kind={kind}")

        assert response.status_code == status_code
        assert response.is_json
        assert response.get_json() == {
            "error": {
                "code": code,
                "message": message,
                "details": {},
            }
        }

    def test_paginated_collection_response_includes_standard_metadata(self, client):
        """Collection payloads should include consistent pagination metadata."""
        response = client.get("/api/v1/__tests__/paginated")

        assert response.status_code == 200
        assert response.is_json
        assert response.get_json() == {
            "items": [
                {"id": 3, "name": "Item 3"},
                {"id": 4, "name": "Item 4"},
            ],
            "pagination": {
                "page": 2,
                "per_page": 2,
                "total": 5,
                "pages": 3,
                "has_next": True,
                "has_prev": True,
            },
        }

    def test_validation_error_returns_422_with_field_details(self, client):
        """Marshmallow ValidationErrors should map to 422 with field-level detail."""
        response = client.get("/api/v1/__tests__/validation-error")

        assert response.status_code == 422
        assert response.is_json
        assert response.get_json() == {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed.",
                "details": {"name": ["Missing data for required field."]},
            }
        }

    def test_wrong_method_on_api_route_returns_json_405(self, client):
        """Using the wrong HTTP method on an API route should return a JSON 405."""
        response = client.post("/api/v1/health")

        assert response.status_code == 405
        assert response.is_json
        assert response.get_json()["error"]["code"] == "METHOD_NOT_ALLOWED"
