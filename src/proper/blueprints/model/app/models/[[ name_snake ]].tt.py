import peewee as pw

from .base import BaseModel


class [[ name_pascal ]](BaseModel):
    [%- for row in rows %]
    [[ row | safe ]]
    [%- endfor %]
