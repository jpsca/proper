from typing import TYPE_CHECKING

from ..constants import FLASHES_SESSION_KEY

if TYPE_CHECKING:
    from typing import Any
    from proper import Response


ALERT = "alert"
ERROR = "error"
NOTICE = "notice"
DICT_ATTRS = ("keys", "get", "items", "update", "setdefault", "values")


class FlashDict:
    def __init__(self, response: "Response") -> None:
        self.response = response

    @property
    def dict(self) -> dict:
        if FLASHES_SESSION_KEY not in self.response.session:
            self.response.session[FLASHES_SESSION_KEY] = {}
        return self.response.session[FLASHES_SESSION_KEY]

    def __getattr__(self, name: str) -> str:
        if name in DICT_ATTRS:
            return getattr(self.dict, name)
        return super().__getattr__(name)

    def __setitem__(self, key: str, value: "Any") -> None:
        self.dict[key] = value

    def __delitem__(self, key: str) -> None:
        self.dict.__delitem__(key)

    def __contains__(self, key: str) -> bool:
        return key in self.dict

    def alert(self, message: str) -> None:
        self[ALERT] = message

    def error(self, message: str) -> None:
        self[ERROR] = message

    def notice(self, message: str) -> None:
        self[NOTICE] = message
