class BaseAttachment:  # noqa
    name = None
    obj = None

    def __init__(self, service=None, variants=None):
        self.service = service
        self.variants = variants

    def attach(
        self,
        filesto=None,
        *,
        io=None,
        filename: str = None,
        content_type: str = None,
        identify: bool = False,
    ):
        pass

    def purge(self):
        pass

    def purge_later(self):
        pass

    def download(self):
        pass

    def show(self):
        pass

    def __repr__(self):
        cls = self.__class__.__name__
        if self.obj is None:
            return f"<{cls}>"
        model_id = getattr(self.obj, "id", None)
        model = self.obj.__class__.__name__
        return f"<{cls} {model}#{model_id}.{self.name}>"


class Attachment(BaseAttachment):
    pass


class AttachmentList(BaseAttachment):
    def __init__(self):
        super().__init__()
