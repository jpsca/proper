import peewee as pw

from app.models.base import BaseMixin


class Timestamped(BaseMixin):
    created_at = pw.DateTimeField(default=pw.utcnow, null=True)
    updated_at = pw.DateTimeField(default=pw.utcnow, null=True)

    @classmethod
    def update(cls, *args, **kwargs):
        kwargs["updated_at"] = pw.utcnow()
        return super().update(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.updated_at = pw.utcnow()
        return super().save(*args, **kwargs)
