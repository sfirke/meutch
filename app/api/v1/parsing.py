"""Shared request-data loading helpers for API v1."""

from flask import request


def load_json_data(schema):
    """Load and validate a JSON request body with the provided schema."""
    return schema.load(request.get_json(silent=True) or {})


def load_query_data(schema):
    """Load and validate query parameters with the provided schema."""
    return schema.load(request.args)
