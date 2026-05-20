"""Shared Marshmallow schema primitives for the API."""

import json

from marshmallow import Schema, ValidationError, fields, pre_load, validate
from werkzeug.datastructures import FileStorage

_JSON_NOT_PARSED = object()
_API_BOOLEAN_TRUTHY = {
    True,
    1,
    "1",
    "true",
    "True",
    "TRUE",
    "t",
    "T",
    "yes",
    "Yes",
    "YES",
    "y",
    "Y",
    "on",
    "On",
    "ON",
}
_API_BOOLEAN_FALSY = {
    False,
    0,
    "0",
    "false",
    "False",
    "FALSE",
    "f",
    "F",
    "no",
    "No",
    "NO",
    "n",
    "N",
    "off",
    "Off",
    "OFF",
}


class ApiBoolean(fields.Boolean):
    """Boolean field with stable HTML and mobile string coercion."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("truthy", _API_BOOLEAN_TRUTHY)
        kwargs.setdefault("falsy", _API_BOOLEAN_FALSY)
        super().__init__(*args, **kwargs)


class ApiUploadedFile(fields.Field):
    """Validate an uploaded file while preserving the original FileStorage object."""

    def _deserialize(self, value, attr, data, **kwargs):
        if value is None:
            return None

        if not isinstance(value, FileStorage):
            raise ValidationError("Not a valid uploaded file.")

        if not (value.filename or "").strip():
            raise ValidationError("Not a valid uploaded file.")

        return value


def validate_location_method_fields(data):
    """Require address or coordinate fields based on the selected location method."""
    location_method = data.get("location_method")
    errors = {}

    if location_method == "address":
        for field_name in ("street", "city", "state", "zip_code", "country"):
            field_value = data.get(field_name)
            if field_value is None or not str(field_value).strip():
                errors[field_name] = ["This field is required when location_method is 'address'."]

    if location_method == "coordinates":
        for field_name in ("latitude", "longitude"):
            if data.get(field_name) is None:
                errors[field_name] = [
                    "This field is required when location_method is 'coordinates'."
                ]

    if errors:
        raise ValidationError(errors)


class ApiSchema(Schema):
    """Base schema for API request and response serialization."""

    @pre_load
    def normalize_multidict(self, data, **kwargs):
        """Normalize MultiDict-style inputs for schema loading."""
        if hasattr(data, "lists"):
            raw_data = {key: values for key, values in data.lists()}
        elif isinstance(data, dict):
            raw_data = data
        else:
            return data

        return {
            key: self._normalize_input_value(
                self.fields.get(self._get_field_name_for_input_key(key)),
                value,
            )
            for key, value in raw_data.items()
        }

    def _normalize_input_value(self, field, value):
        if isinstance(value, list):
            if isinstance(field, fields.List):
                return self._normalize_list_value(field, value)
            return self._normalize_scalar_value(field, value[-1] if value else None)

        return self._normalize_scalar_value(field, value)

    def _normalize_list_value(self, field, value):
        normalized_values = [entry for entry in value if not self._is_empty_upload(entry)]

        if len(normalized_values) == 1:
            parsed_value = self._parse_json_value(field, normalized_values[0])
            if parsed_value is not _JSON_NOT_PARSED:
                return parsed_value

        return normalized_values

    def _normalize_scalar_value(self, field, value):
        if self._is_empty_upload(value):
            return None

        parsed_value = self._parse_json_value(field, value)
        if parsed_value is not _JSON_NOT_PARSED:
            return parsed_value

        if isinstance(value, str):
            return value.strip()

        return value

    def _parse_json_value(self, field, value):
        if not isinstance(value, str) or field is None:
            return _JSON_NOT_PARSED

        stripped_value = value.strip()
        if not stripped_value:
            return _JSON_NOT_PARSED

        if isinstance(field, fields.List) and stripped_value.startswith("["):
            return self._load_json_value(stripped_value, list)

        if isinstance(field, fields.Nested) and stripped_value.startswith("{"):
            return self._load_json_value(stripped_value, dict)

        return _JSON_NOT_PARSED

    def _load_json_value(self, value, expected_type):
        try:
            parsed_value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return _JSON_NOT_PARSED

        if not isinstance(parsed_value, expected_type):
            return _JSON_NOT_PARSED

        return parsed_value

    def _is_empty_upload(self, value):
        return isinstance(value, FileStorage) and not (value.filename or "").strip()

    def _get_field_name_for_input_key(self, key):
        for field_name, field in self.fields.items():
            if field.data_key == key:
                return field_name
        return key


class ApiDateTime(fields.DateTime):
    """Datetime field that always emits ISO 8601 strings."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("format", "iso")
        super().__init__(*args, **kwargs)


class LocationFieldsMixin:
    """Shared optional location fields for schemas that accept address or coordinate input."""

    street = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=200))
    city = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    state = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=100))
    zip_code = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=20),
    )
    country = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(max=100),
    )
    latitude = fields.Float(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=-90, max=90),
    )
    longitude = fields.Float(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=-180, max=180),
    )
