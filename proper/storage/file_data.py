class FileData:
    id: int = 0
    key: str = ""
    service_name: str = ""
    filename: str = ""
    byte_size: int = 0
    content_type: str = ""
    checksum: str = ""
    data: dict

    def __init__(self, **kw):
        self.data = {}
        self.update(**kw)

    def update(self, **kw):
        for name, value in kw.items():
            setattr(self, name, value)
