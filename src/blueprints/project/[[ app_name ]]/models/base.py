import inflection

from ..app import db


def make_table_name(cls):
    return inflection.tableize(cls.__name__)


class BaseModel(Model):
    class Meta:
        database = db
        table_function = make_table_name
