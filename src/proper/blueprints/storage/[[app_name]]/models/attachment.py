from ..main import app
from .base import BaseModel


class Attachment(app.attachment_for(BaseModel)):
    # You can add any extra fields here, like:
    # user = pw.ForeignKeyField(User, null=True)
    # etc.
    ...
