import typing as t
from collections.abc import Iterator

from ...constants import FLASHES_SESSION_KEY


if t.TYPE_CHECKING:
    from . import Response


class FlashMessages:
    def __init__(self, response: "Response"):
        self.response = response
        if FLASHES_SESSION_KEY not in self.response.session:
            self.response.session[FLASHES_SESSION_KEY] = []

    @property
    def flashes(self) -> list[tuple[str, str]]:
        return self.response.session.get(FLASHES_SESSION_KEY, [])

    @flashes.setter
    def flashes(self, value: list[tuple[str, str]]) -> None:
        self.response.session[FLASHES_SESSION_KEY] = value

    def __getitem__(self, index: int) -> t.Any:
        return self.flashes.__getitem__(index)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return self.flashes.__iter__()

    def __len__(self) -> int:
        return len(self.flashes)

    def message(self, category: str, message: str) -> None:
        self.response.session.setdefault(FLASHES_SESSION_KEY, []).append(
            (category, message)
        )
