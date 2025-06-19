import peewee as pw

from app.main import app


db = app.db["main"]


class BaseModel(pw.Model):
    class Meta:
        database = app.db["main"]


class BaseMixin(pw.Model):
    class Meta:
        database = app.db["main"]
