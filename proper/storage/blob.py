class Blob:
    __slots__ = [
        "id",
        "key",
        "service_name",
        "filename",
        "byte_size",
        "content_type",
        "checksum",
        "data",
    ]

    def __init__(self, **kw):
        self.id: int = str(kw.get("id", 0))
        self.key: str = str(kw.get("key", ""))
        self.service_name: str = str(kw.get("service_name", ""))
        self.filename: str = str(kw.get("filename", ""))
        self.byte_size: int = int(kw.get("byte_size", 0))
        self.content_type: str = str(kw.get("content_type", ""))
        self.checksum: str = str(kw.get("checksum", ""))
        self.data: dict = dict(kw.get("data", {}))
