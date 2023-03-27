import typing as t

from proper.request.multipart import MultipartPart


TUpload = MultipartPart | t.BinaryIO


class TAttachment:
    key: str
    service_name: str
    byte_size: int | None
    content_type: str | None
    checksum: str | None
    filename: str

    def delete_instance(self) -> None:
        ...
