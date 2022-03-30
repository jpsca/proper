from sqla_wrapper import BaseModel

from .attachment import Attachment, AttachmentList, BaseAttachment


__all__ = ("attach_one", "attach_many", "Attachable", "AttachableBaseModel")


def attach_one(*args, **kwargs):
    return Attachment()


def attach_many(*args, **kwargs):
    return AttachmentList(*args, **kwargs)


class Attachable:
    def __new__(cls, **kwargs):
        obj = super().__new__(cls, **kwargs)
        for key, col in cls.__dict__.items():
            if isinstance(col, BaseAttachment):
                col.name = key
                col.obj = obj
                if key in kwargs:
                    col.attach(kwargs[key])
        return obj


class AttachableBaseModel(BaseModel):
    pass
