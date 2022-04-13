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
        self.id = ""
        self.key = ""
        self.service_name = ""
        self.filename = ""
        self.byte_size = 0
        self.content_type = ""
        self.checksum = ""
        self.data = {}
        self.__dict__.update(kw)
