from sqla_wrapper import BaseModel

from .attachment import BaseAttachment


__all__ = ("AttachableBase", )


class AttachableBase(BaseModel):
    def __new__(cls) -> "AttachableBase":
        obj = super().__new__(cls)
        for key, value in cls.__dict__.items():
            if isinstance(value, BaseAttachment):
                value.column_name = key
                value.obj = obj
        return obj
