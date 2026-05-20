"""Shared request-data loading helpers for API v1."""

from flask import request
from werkzeug.datastructures import CombinedMultiDict

_FORM_CONTENT_TYPES = {
    "application/x-www-form-urlencoded",
    "multipart/form-data",
}


def load_request_data(schema):
    """Load and validate a write request body with the provided schema."""
    return schema.load(_get_request_input())


def load_query_data(schema):
    """Load and validate query parameters with the provided schema."""
    return schema.load(request.args)


def _get_request_input():
    if request.is_json:
        return request.get_json(silent=True) or {}

    if request.mimetype in _FORM_CONTENT_TYPES or request.form or request.files:
        return CombinedMultiDict((request.form, request.files))

    return {}
