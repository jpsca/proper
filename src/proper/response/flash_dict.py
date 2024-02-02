import typing as t

from ..constants import FLASHES_SESSION_KEY


if t.TYPE_CHECKING:
    from ..response import Response


ALERT = "alert"
ERROR = "error"
NOTICE = "notice"
DICT_ATTRS = ("dict", "keys", "get", "items", "update", "setdefault", "values")


class FlashDict:
    def __init__(self, response: "Response"):
        self.response = response

    def __getattr__(self, name: str) -> t.Any:
        if name in DICT_ATTRS:
            return self.get_dict().get(name)
        raise AttributeError(name)

    def __setitem__(self, key: str, value: t.Any) -> None:
        self.get_dict()[key] = value

    def __delitem__(self, key: str) -> None:
        self.get_dict().__delitem__(key)

    def __contains__(self, key: str) -> bool:
        return key in self.get_dict()

    def alert(self, message: str) -> None:
        self[ALERT] = message

    def error(self, message: str) -> None:
        self[ERROR] = message

    def notice(self, message: str) -> None:
        self[NOTICE] = message

    def get_dict(self) -> dict[str, t.Any]:
        if FLASHES_SESSION_KEY not in self.response.session:
            self.response.session[FLASHES_SESSION_KEY] = {}
        return self.response.session[FLASHES_SESSION_KEY]
