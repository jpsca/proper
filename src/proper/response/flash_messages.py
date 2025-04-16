import typing as t

from ..constants import FLASHES_SESSION_KEY


if t.TYPE_CHECKING:
    from . import Response


class FlashMessages:
    def __init__(self, response: "Response"):
        self.response = response
        if FLASHES_SESSION_KEY not in self.response.session:
            self.response.session[FLASHES_SESSION_KEY] = []

    @property
    def flashes(self) -> list[tuple[str, str]]:
        return self.response.session[FLASHES_SESSION_KEY]

    def __getitem__(self, index: int) -> t.Any:
        return self.flashes.__getitem__(index)

    def __iter__(self) -> t.Iterator[tuple[str, str]]:
        return self.flashes.__iter__()

    def __len__(self) -> int:
        return len(self.flashes)

    def message(self, type: str, message: str) -> None:
        self.flashes.append((type, message))
