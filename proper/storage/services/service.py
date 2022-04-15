from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import IO
    from proper import App
    from ..blob import Blob


class Service:
    """Abstract class serving as an interface for concrete services.
    """

    def __init__(self, app: "App", **kw) -> None:
        self.app = app
        self.config = kw

    def save(self, filesto: "IO", blob: "Blob") -> "Blob":
        raise NotImplementedError
