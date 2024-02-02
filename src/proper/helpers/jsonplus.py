import datetime
import json
from typing import Any


__all__ = ("dumps", "loads")

DATE_PREFIX = "__dt__"


class CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> str:
        if isinstance(o, datetime.date):
            return f"{DATE_PREFIX}{o.isoformat()}"
        return super().default(o)


class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args, **kw) -> None:
        kw["object_hook"] = self.try_datetime
        super().__init__(*args, **kw)

    @staticmethod
    def try_datetime(d: dict) -> dict:
        ret = {}
        for key, value in d.items():
            if isinstance(value, str) and value.startswith(DATE_PREFIX):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    pass
            ret[key] = value
        return ret


def dumps(obj: Any, **kw) -> str:
    kw["cls"] = CustomEncoder
    return json.dumps(obj, **kw)


def loads(s: str, **kw) -> dict:
    kw["cls"] = CustomDecoder
    return json.loads(s, **kw)
