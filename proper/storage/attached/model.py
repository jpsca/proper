from sqla_wrapper import BaseModel

from .one import AttachedOne


__all__ = ("AttachableBase", )


class AttachableBase(BaseModel):
    def __new__(cls, **kw) -> "AttachableBase":
        obj = super().__new__(cls)
        for key, value in cls.__dict__.items():
            if isinstance(value, AttachedOne):
                value.column_name = key
                value.obj = obj
        obj.__init__(**kw)
        return obj
