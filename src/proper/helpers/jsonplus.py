import datetime
import json
from typing import Any


__all__ = ("dumps", "loads")


class CustomEncoder(json.JSONEncoder):
    def default(self, obj: "Any") -> str:
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        return super().default(obj)


class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args, **kw) -> None:
        kw["object_hook"] = self.try_datetime
        super().__init__(*args, **kw)

    @staticmethod
    def try_datetime(d: dict) -> dict:
        ret = {}
        for key, value in d.items():
            try:
                ret[key] = datetime.datetime.fromisoformat(value)
            except (ValueError, TypeError):
                ret[key] = value
        return ret


def dumps(obj: "Any", **kw) -> str:
    kw["cls"] = CustomEncoder
    return json.dumps(obj, **kw)


def loads(s: str, **kw) -> dict:
    kw["cls"] = CustomDecoder
    return json.loads(s, **kw)
