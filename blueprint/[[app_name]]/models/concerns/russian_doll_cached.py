from proper.models import after_save, before_delete, utcnow

from ..base import BaseModel
from .timestamped import Timestamped


class RussianDollCached(Timestamped, BaseModel):
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
    any `{% cache(post) %}` fragment that wraps `{% cache(comment) %}`.
    """

    # Tuple of ForeignKeyField names whose parent records should be
    # touched when this record is saved or deleted.
    touches: tuple[str, ...] = ()

    def touch(self):
        """Bump this record's `updated_at` and propagate to `touches`."""
        type(self).update(updated_at=utcnow()).where(
            type(self)._meta.primary_key == self.get_id()
        ).execute()
        self._touch_related()

    @after_save
    @before_delete
    def _touch_related(self):
        for field_name in self.touches:
            related = getattr(self, field_name, None)
            if related is not None and hasattr(related, "touch"):
                related.touch()
