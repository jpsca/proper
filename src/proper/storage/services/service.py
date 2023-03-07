import typing as t


if t.TYPE_CHECKING:
    from ...app import App
    from ...helpers import DotDict
    from ..types import TAttachment, TUpload


class Service:
    """Abstract class serving as an interface for concrete services."""

    def __init__(self,  app: "App", config: "DotDict") -> None:
        self.config = config

    def upload(
        self,
        obj: "TAttachment",
        filesto: "TUpload",
        filename: str,
        content_type: str,
        byte_size: int,
    ) -> None:
        raise NotImplementedError

    def download_to_tempfile(self, obj: "TAttachment") -> str:
        raise NotImplementedError
