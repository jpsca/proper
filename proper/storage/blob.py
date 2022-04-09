from typing import Any


class Blob:
    id: str = ""
    key: str = ""
    service_name: str = ""
    filename: str = ""
    byte_size: int = 0
    content_type: str = ""
    checksum: str = ""
    metadata: Any

    def __init__(self, **kw):
        kw.setdefault("metadata", {})
        self.__dict__.update(kw)
