import typing as t

import peewee as pw

from .scopes import ScopesMixin
from .signals import SignalsMixin
from .tokens import TokensMixin


# The SQL of `find` per model and database, generated once. Building it is
# most of what a lookup by primary key costs; the text never changes.
_FIND_SQL: dict[tuple[type, t.Any], str] = {}


class ProperModel(ScopesMixin, SignalsMixin, TokensMixin, pw.Model):
    """Base Peewee model with extra features: scope support, signals, and token generation."""
    @classmethod
    def find(cls, pk: t.Any) -> t.Any:
        """The row with this primary key, or `None`.

        Like `get_or_none(Model.id == pk)`, but the SQL is generated once
        per model instead of on every call, which is most of the cost of a
        lookup this simple. No scopes apply: this is the direct lookup a
        `show`, `edit` or `update` action does.

        ```python
        post = Post.find(self.params["id"])
        if post is None:
            raise NotFound
        ```
        """
        if pk is None:
            return None
        field = cls._meta.primary_key
        if field is False:
            raise ValueError(f"{cls.__name__} has no primary key")
        database = cls._meta.database
        sql = _FIND_SQL.get((cls, database))
        if sql is None:
            # The same text Peewee generates for this database (quoting,
            # alias, parameter style), with the primary key as the parameter.
            sql, params = cls.select().where(field == 0).sql()
            assert len(params) == 1, params
            _FIND_SQL[(cls, database)] = sql
        for obj in cls.raw(sql, field.db_value(pk)):
            return obj
        return None
