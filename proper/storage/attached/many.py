from typing import TYPE_CHECKING

from .attached import Attached

if TYPE_CHECKING:
    from typing import IO, Union
    from multipart import MultipartPart


class AttachedMany(Attached):
    def attach(
        self,
        *,
        filename: str = "",
        content_type: str = "",
        byte_size: int = 0,
        **filesto_list: "Union[MultipartPart, IO]",
    ) -> None:
        for filesto in filesto_list:
            return super().attach(
                filesto=filesto,
                filename=filename,
                content_type=content_type,
                byte_size=byte_size,
            )
