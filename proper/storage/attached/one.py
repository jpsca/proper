from typing import TYPE_CHECKING

from .attached import Attached

if TYPE_CHECKING:
    from typing import IO, Union
    from multipart import MultipartPart


class AttachedOne(Attached):
    def attach(
        self,
        filesto: "Union[MultipartPart, IO]",
        *,
        filename: str = "",
        content_type: str = "",
        byte_size: int = 0,
    ) -> None:
        return super().attach(
            filesto=filesto,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
        )

    def download(self):
        pass

    def show(self):
        pass

    def get_blob(self):
        """meh"""
        row = self.storage.get_blobs(
            model_type=self.model_type,
            model_id=self.model_id,
            column_name=self.column_name,
        )[-1]
        return row._mapping
