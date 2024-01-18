from datetime import datetime

from peewee import DateTimeField
from [[ app_name ]].models.base import BaseMixin


class Timestamped(BaseMixin):
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    @classmethod
    def update(cls, model, *args, **kwargs):
        model.updated_at = datetime.utcnow()
        return super().update(*args, **kwargs)
