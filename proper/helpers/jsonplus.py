import datetime
import json
from typing import Any


__all__ = ("dumps", "loads")


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return obj.isoformat()


class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.try_datetime, *args, **kwargs)

    @staticmethod
    def try_datetime(d):
        ret = {}
        for key, value in d.items():
            try:
                ret[key] = datetime.datetime.fromisoformat(value)
            except (ValueError, TypeError):
                ret[key] = value
        return ret


def dumps(obj: Any, **kwargs):
    kwargs["cls"] = CustomEncoder
    return json.dumps(obj, **kwargs)


def loads(s: str, **kwargs):
    kwargs["cls"] = CustomDecoder
    return json.loads(s, **kwargs)
