"""A connection to MySQL that records the queries instead of running them.

A query that reads the schema is answered with the rows of `results`
whose key is part of the query.
"""

__all__ = ("RecordingConnection",)


class RecordingCursor:
    rowcount = 0
    description = None

    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, *args, **kwargs):
        self.connection.queries.append(query)
        self.rows = []
        for text, rows in self.connection.results.items():
            if text in query:
                self.rows = rows

    def __iter__(self):
        return iter(self.rows)

    def fetchall(self, *args, **kwargs):
        return list(self.rows)

    def close(self):
        pass


class RecordingConnection:
    server_version = "8.4.0"

    def __init__(self, **params):
        self.params = params
        self.queries = []
        self.results = {}

    def cursor(self, *args, **kwargs):
        return RecordingCursor(self)

    def close(self):
        pass
