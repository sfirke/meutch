"""Integration tests for shared API error and response helpers."""

from io import BytesIO

import pytest
from flask import request
from marshmallow import ValidationError, fields
from werkzeug.datastructures import MultiDict

from app.api.v1 import bp as api_v1_bp
from app.api.v1.parsing import load_request_data
from app.api.v1.responses import build_collection_response
from app.api.v1.schemas.base import ApiBoolean, ApiSchema, ApiUploadedFile
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


class ApiTestLinkSchema(ApiSchema):
    """Schema used to exercise list and JSON form parsing in API tests."""

    platform = fields.String(required=True)
    url = fields.String(required=True)


class ApiTestParsedBodySchema(ApiSchema):
    """Schema used to verify shared request parsing across content types."""

    enabled = ApiBoolean(required=True)
    tags = fields.List(fields.String(), required=True)
    links = fields.List(fields.Nested(ApiTestLinkSchema()), load_default=list)
    images = fields.List(ApiUploadedFile(), load_default=list)


TEST_PARSED_BODY_SCHEMA = ApiTestParsedBodySchema()


@api_v1_bp.post("/__tests__/parsed-body")
def api_test_parsed_body():
    """Echo parsed request data so parsing behavior can be asserted end to end."""
    data = load_request_data(TEST_PARSED_BODY_SCHEMA)
    return {
        "enabled": data["enabled"],
        "tags": data["tags"],
        "links": data["links"],
        "image_names": [uploaded_file.filename for uploaded_file in data["images"]],
    }


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

    def test_body_parser_loads_multipart_lists_files_and_json_arrays(self, client):
        """Multipart bodies should preserve repeated values, uploads, and JSON list fields."""
        response = client.post(
            "/api/v1/__tests__/parsed-body",
            data=MultiDict(
                [
                    ("enabled", "on"),
                    ("tags", "ladders"),
                    ("tags", "paint"),
                    (
                        "links",
                        '[{"platform": "website", "url": "https://example.com/help"}]',
                    ),
                    ("images", (BytesIO(b"file-one"), "first.jpg")),
                    ("images", (BytesIO(b"file-two"), "second.jpg")),
                ]
            ),
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "enabled": True,
            "tags": ["ladders", "paint"],
            "links": [{"platform": "website", "url": "https://example.com/help"}],
            "image_names": ["first.jpg", "second.jpg"],
        }

    def test_body_parser_validation_errors_use_shared_422_response(self, client):
        """Schema validation failures from the shared parser should keep the API error shape."""
        response = client.post(
            "/api/v1/__tests__/parsed-body",
            data={"enabled": "sometimes"},
            content_type="application/x-www-form-urlencoded",
        )

        assert response.status_code == 422
        assert response.get_json() == {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed.",
                "details": {
                    "enabled": ["Not a valid boolean."],
                    "tags": ["Missing data for required field."],
                },
            }
        }

    def test_wrong_method_on_api_route_returns_json_405(self, client):
        """Using the wrong HTTP method on an API route should return a JSON 405."""
        response = client.post("/api/v1/health")

        assert response.status_code == 405
        assert response.is_json
        assert response.get_json()["error"]["code"] == "METHOD_NOT_ALLOWED"
