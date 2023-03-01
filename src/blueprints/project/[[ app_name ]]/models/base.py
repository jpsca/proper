import inflection
from peewee import Model

from ..app import app


def make_table_name(cls):
    return inflection.tableize(cls.__name__)


class BaseModel(Model):
    class Meta:
        database = app.db
        table_function = make_table_name


class BaseMixin(Model):
    class Meta:
        database = app.db
        table_function = make_table_name
