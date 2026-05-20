"""Shared Marshmallow schema primitives for the API."""

from marshmallow import Schema, fields, pre_load


class ApiSchema(Schema):
    """Base schema for API response serialization."""

    @pre_load
    def normalize_multidict(self, data, **kwargs):
        """Normalize MultiDict-style inputs for schema loading."""
        if hasattr(data, "lists"):
            raw_data = {key: values for key, values in data.lists()}
        elif isinstance(data, dict):
            raw_data = data
        else:
            return data

        normalized = {}
        for key, value in raw_data.items():
            field_name = self._get_field_name_for_input_key(key)
            field = self.fields.get(field_name)

            if isinstance(value, list):
                if isinstance(field, fields.List):
                    normalized[key] = value
                else:
                    normalized[key] = value[-1] if value else None
            else:
                normalized[key] = value

        return normalized

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
