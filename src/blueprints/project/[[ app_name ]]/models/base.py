import inflection
from peewee import ModelBase

from ..app import app


def make_table_name(cls):
    return inflection.tableize(cls.__name__)


class BaseModel(ModelBase):
    class Meta:
        database = app.db
        table_function = make_table_name
