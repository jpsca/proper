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
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(object_hook=self.try_datetime, *args, **kwargs)

    @staticmethod
    def try_datetime(d: dict) -> dict:
        ret = {}
        for key, value in d.items():
            try:
                ret[key] = datetime.datetime.fromisoformat(value)
            except (ValueError, TypeError):
                ret[key] = value
        return ret


def dumps(obj: "Any", **kwargs) -> str:
    kwargs["cls"] = CustomEncoder
    return json.dumps(obj, **kwargs)


def loads(s: str, **kwargs) -> dict:
    kwargs["cls"] = CustomDecoder
    return json.loads(s, **kwargs)
