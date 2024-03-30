from datetime import datetime

import peewee as pw

from [[ app_name ]].models.base import BaseMixin


class Timestamped(BaseMixin):
    created_at = pw.DateTimeField(default=datetime.utcnow, null=True)
    updated_at = pw.DateTimeField(default=datetime.utcnow, null=True)

    @classmethod
    def update(cls, model, *args, **kwargs):
        model.updated_at = datetime.utcnow()
        return super().update(*args, **kwargs)
