from datetime import datetime

from peewee import *  # noqa


class Timestamped:
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    @classmethod
    def update(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().update(*args, **kwargs)
