"""Prepared queries: built and compiled to SQL once, executed many times.

Building a Peewee query and compiling it to SQL can cost more than running it,
on SQLite. A prepared query is compiled on its first execution (per database);
the next ones only put the values in place and run the SQL:

```python
from proper.db import Param, prepare

LAST_PAGE = prepare(
    Message.select()
    .where(Message.room == Param("room"))
    .order_by(Message.id.desc())
    .limit(Param("n"))
)

messages = list(LAST_PAGE.execute(room=room.id, n=40))
```

Each value goes through the same conversion the compiler would have applied:
the `db_value()` of the field its `Param` is compared to, assigned or inserted
into. The results are the query's own: model instances, dicts, tuples, joined
models, as it was built. `UPDATE` and `DELETE` work too.

The SQL cannot change between executions, so a `Param` cannot stand for a
list (`IN`), a column or a table, and values that would compile to SQL
(expressions, subqueries) are refused.

This is built on Peewee internals (`Context.value(converter=False)`,
`query._get_cursor_wrapper()`, `handle_result()`), not on its public API; its
tests are what tell whether a new Peewee still works with it.
"""
from peewee import (
    DatabaseProxy,
    InterfaceError,
    Model,
    Node,
    SelectBase,
    _WriteQuery,
    is_model,  # ty: ignore[unresolved-import] - missing from types-peewee
)


__all__ = ("Param", "PreparedQuery", "prepare")


class Param(Node):
    """A named place for a value in a prepared query."""

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "Param(%r)" % (self.name,)

    def __sql__(self, ctx):
        # converter=False: the slot itself goes to the params list, untouched,
        # carrying the converter in effect here, to be applied at execution.
        return ctx.value(_ParamSlot(self.name, ctx.state.converter), converter=False)


class _ParamSlot:
    __slots__ = ("name", "converter")

    def __init__(self, name, converter):
        self.name = name
        self.converter = converter


class _PreparedEntry:
    # A prepared query compiled for one database: its SQL, the parameter list
    # with the fixed values in place, and a slot where each `Param` goes.
    __slots__ = ("database", "sql", "params", "slots", "names")

    def __init__(self, database, sql, params, slots):
        self.database = database
        self.sql = sql
        self.params = params
        self.slots = slots
        self.names = frozenset(name for _, name, _ in slots)


class PreparedQuery:
    """A query compiled once and executed many times with new values.

    The SQL cannot change between executions, so a `Param` cannot stand for
    a list (`IN`), a column or a table, and values that would compile to SQL
    (expressions, subqueries) are refused.
    """

    __slots__ = ("query", "_entry")

    def __init__(self, query):
        if isinstance(query, _WriteQuery) and query._returning:
            raise ValueError("Prepared queries do not support RETURNING.")
        self.query = query
        self._entry = None

    def __repr__(self):
        return "<PreparedQuery %r>" % (self.query,)

    def _compile(self, database):
        sql, params = database.get_sql_context().sql(self.query).query()
        slots = [
            (idx, param.name, param.converter)
            for idx, param in enumerate(params)
            if isinstance(param, _ParamSlot)
        ]
        entry = self._entry = _PreparedEntry(database, sql, params, slots)
        return entry

    def _entry_for(self, database):
        entry = self._entry
        if entry is None or entry.database is not database:
            entry = self._compile(database)
        return entry

    def sql(self, database=None):
        """The SQL and the parameter list, with a `Param` where each value goes."""
        entry = self._entry_for(self._database(database))
        params = list(entry.params)
        for idx, name, _ in entry.slots:
            params[idx] = Param(name)
        return entry.sql, params

    def _database(self, database):
        database = database or self.query._database
        if database is None:
            raise InterfaceError(
                'Query must be bound to a database in order to call "execute()".'
            )
        if isinstance(database, DatabaseProxy):
            database = database.obj
        return database

    def _params(self, entry, values):
        if entry.names.symmetric_difference(values):
            missing = sorted(entry.names.difference(values))
            unknown = sorted(set(values).difference(entry.names))
            raise ValueError(
                "Prepared query values: missing %s, unknown %s." % (missing, unknown)
            )
        params = list(entry.params)
        for idx, name, converter in entry.slots:
            value = values[name]
            # Checked before and after the conversion: an expression would
            # compile to SQL in the query, and a converter may also return one.
            if isinstance(value, Model) or not isinstance(
                value, (Node, list, tuple, set, frozenset)
            ):
                if converter:
                    value = converter(value)
                if not isinstance(value, Node) and not is_model(value):
                    params[idx] = value
                    continue
            raise ValueError(
                "The value of Param(%r) would change the SQL of a prepared query: %r"
                % (name, value)
            )
        return params

    def execute(self, database=None, **values):
        """Run the query with these values for its `Param`s. A SELECT returns
        its results; any other query, what `execute()` would."""
        database = self._database(database)
        entry = self._entry_for(database)
        cursor = database.execute_sql(entry.sql, self._params(entry, values))
        query = self.query
        if not isinstance(query, SelectBase):
            return query.handle_result(database, cursor)
        return query._get_cursor_wrapper(cursor)

    def first(self, database=None, **values):
        """The first row of the results, or `None`."""
        for row in self.execute(database, **values):
            return row
        return None


def prepare(query):
    """Compile `query` once, for executing it many times (see the module)."""
    return PreparedQuery(query)
