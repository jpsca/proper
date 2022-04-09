from sqla_wrapper import BaseModel

from .attachment import BaseAttachment


__all__ = ("Attachable", "AttachableBaseModel")


class Attachable:
    def __new__(cls, **kwargs):
        obj = super().__new__(cls, **kwargs)
        for key, col in cls.__dict__.items():
            if isinstance(col, BaseAttachment):
                col.column_name = key
                col.obj = obj
                if key in kwargs:
                    col.attach(kwargs[key])
        return obj


class AttachableBaseModel(Attachable, BaseModel):
    pass
