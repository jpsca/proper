import peewee as pw

from ..base import BaseModel


class RussianDollCached(BaseModel):
    """A Rails-like russian doll caching mechanism for Peewee models.

    When a model declares `touches`, saving or deleting an instance
    automatically bumps the `updated_at` of related parent records.
    This invalidates the parent's cache key (which includes `updated_at`),
    cascading through nested `{% cache %}` template fragments.

    Example::

        class Comment(RussianDollCached, BaseModel):
            post = pw.ForeignKeyField(Post)
            touches = ("post",)

    Now saving a Comment bumps its Post's `updated_at`, which busts
    any `{% cache post %}` fragment that wraps `{% cache comment %}`.
    """

    updated_at = pw.DateTimeField(default=pw.utcnow, null=True)

    # Tuple of ForeignKeyField names whose parent records should be
    # touched when this record is saved or deleted.
    touches: tuple[str, ...] = ()

    @classmethod
    def update(cls, *args, **kwargs):
        kwargs["updated_at"] = pw.utcnow()
        return super().update(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.updated_at = pw.utcnow()
        result = super().save(*args, **kwargs)
        self._touch_related()
        return result

    def delete_instance(self, *args, **kwargs):
        self._touch_related()
        return super().delete_instance(*args, **kwargs)

    def touch(self):
        """Bump this record's `updated_at` and propagate to `touches`."""
        type(self).update(updated_at=pw.utcnow()).where(
            type(self)._meta.primary_key == self.get_id()
        ).execute()
        self._touch_related()

    def _touch_related(self):
        for field_name in self.touches:
            related = getattr(self, field_name, None)
            if related is not None and hasattr(related, "touch"):
                related.touch()
