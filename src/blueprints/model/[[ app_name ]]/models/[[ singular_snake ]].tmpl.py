from peewee import *  # noqa

from [[ app_name ]].models.base import BaseModel


class [[ singular_pascal ]](BaseModel):
    [%- for row in rows %]
    [[ row | safe ]]
    [%- endfor %]
