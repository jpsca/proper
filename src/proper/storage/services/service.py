import typing as t


if t.TYPE_CHECKING:
    from proper.core import App
    from proper.helpers import DotDict

    from ..types import TAttachment, TUpload


class Service:
    """Abstract class serving as an interface for concrete services."""

    def __init__(self, app: "App", config: "DotDict") -> None:
        self.config = config

    def upload(self, filesto: "TUpload", obj: "TAttachment") -> None:
        raise NotImplementedError

    def download(self, obj: "TAttachment") -> bytes:
        raise NotImplementedError

    def send_file(self, obj: "TAttachment") -> bytes:
        raise NotImplementedError

    def purge(self, obj: "TAttachment") -> None:
        raise NotImplementedError
