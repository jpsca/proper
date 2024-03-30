import peewee as pw

from .base import BaseModel


class [[ singular_pascal ]](BaseModel):
    [%- for row in rows %]
    [[ row | safe ]]
    [%- endfor %]
