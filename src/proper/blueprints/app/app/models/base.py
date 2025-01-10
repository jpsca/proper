import peewee as pw

from app.main import app


class BaseModel(pw.Model):
    class Meta:
        database = app.db


class BaseMixin(pw.Model):
    class Meta:
        database = app.db
