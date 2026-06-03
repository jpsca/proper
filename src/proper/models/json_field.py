import typing as t

import peewee as pw

from ..helpers import jsonplus


class JSONField(pw.TextField):
    """A TextField-based Peewee field that transparently
    serializes/deserializes JSON data."""

    field_type = "JSON"

    def db_value(self, value: dict | list | None) -> str | None:
        if value is None:
            return None

        ensure_ascii = getattr(self.model._meta.database, "json_ensure_ascii", True)
        if getattr(self.model._meta.database, "json_use_detailed", False):
            indent = 2
        else:
            indent = 0

        return jsonplus.dumps(value, ensure_ascii=ensure_ascii, indent=indent)

    def python_value(self, value) -> dict[str, t.Any] | list[t.Any] | None:
        if value is None:
            return None
        try:
            return jsonplus.loads(value)
        except jsonplus.JSONDecodeError:
            return None
