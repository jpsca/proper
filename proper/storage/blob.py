from typing import Optional, Union


class Blob:
    __slots__ = [
        "key",
        "id",
        "service_name",
        "filename",
        "byte_size",
        "content_type",
        "checksum",
        "data",
    ]

    def __init__(self, **kw):
        self.key: str = kw.get("key", "")
        self.id: "Union[str, int, None]" = kw.get("id", None)
        self.service_name: "Optional[str]" = kw.get("service_name", None)
        self.filename: "Optional[str]" = kw.get("filename", None)
        self.byte_size: int = kw.get("byte_size", 0)
        self.content_type: "Optional[str]" = kw.get("content_type", None)
        self.checksum: "Optional[str]" = kw.get("checksum", None)
        self.data: "Optional[dict]" = kw.get("data", {})
