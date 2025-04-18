import typing as t


if t.TYPE_CHECKING:
    from proper.core.app import App
    from proper.types import TAttachment, TUpload


class Service:
    """Abstract class serving as an interface for concrete services."""

    def __init__(self, app: "App", config: dict[str, t.Any]) -> None:
        self.config = config

    def upload(self, filesto: "TUpload", obj: "TAttachment") -> None:
        raise NotImplementedError

    def download(self, obj: "TAttachment") -> bytes:
        raise NotImplementedError

    def send_file(self, obj: "TAttachment") -> bytes:
        raise NotImplementedError

    def purge(self, obj: "TAttachment") -> None:
        raise NotImplementedError
