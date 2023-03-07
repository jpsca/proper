import typing as t
from datetime import datetime

from multipart import MultipartPart


TUpload = MultipartPart | t.BinaryIO

class TAttachment:
    id: int | None
    key: str | None
    service_name: str | None
    byte_size: int | None
    content_type: str | None
    checksum: str | None
    data: str | None
    filename: str | None
    created_at: datetime| None
