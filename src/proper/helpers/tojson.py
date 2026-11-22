import datetime
import json
import typing as t


__all__ = ("to_json",)


def _default(value: t.Any) -> str:
    if isinstance(value, datetime.date):
        return value.isoformat()
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


_encoder = json.JSONEncoder(default=_default)


def to_json(value: t.Any) -> str:
    """`value` as JSON text, like `json.dumps(value)`, with the `date` and
    `datetime` values written as ISO 8601 strings:

    ```python
    to_json({"day": date(2026, 11, 22)})  # '{"day": "2026-11-22"}'
    ```

    Read it back with `json.loads`: a date comes back as a string.
    """
    return _encoder.encode(value)
