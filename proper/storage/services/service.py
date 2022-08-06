from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import IO, Union

    from multipart import MultipartPart
    from proper import App

    from ..file_data import FileData


class Service:
    """Abstract class serving as an interface for concrete services."""

    def __init__(self, app: "App", **kw) -> None:
        self.app = app
        self.config = kw

    def upload(
        self, filesto: "Union[MultipartPart, IO]", fdata: "FileData"
    ) -> "FileData":
        raise NotImplementedError

    def download_to_tempfile(self, fdata: "FileData") -> str:
        raise NotImplementedError
