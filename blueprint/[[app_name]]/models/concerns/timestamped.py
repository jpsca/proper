import peewee as pw
from proper.models import before_save, utcnow

from ..base import BaseModel


class Timestamped(BaseModel):
    """Adds `updated_at` timestamp to Peewee models.
    """

    updated_at = pw.DateTimeField(default=utcnow, null=True)

    @before_save
    def _set_updated_at(self):
        self.updated_at = utcnow()
