from peewee import *  # noqa

from ..app import app
from .base import BaseModel


class Attachment(app.storage.Attachment, BaseModel):
    ...
