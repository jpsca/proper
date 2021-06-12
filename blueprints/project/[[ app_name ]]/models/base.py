from liquid_orm import DatabaseManager, Model

from ..config import config
from .mixins import Representable


__all__ = ("db", "Model", "Base")

db = DatabaseManager(config.databases)
Model.set_connection_resolver(db)


class Base(Representable, Model):
    def set_defaults(self):
        pass

    def save(self, *args, **kwargs):
        self.set_defaults()
        super().save(*args, **kwargs)
