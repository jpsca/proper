"""A connection to Postgres that records the queries instead of running them."""

from psycopg.pq import TransactionStatus


__all__ = ("RecordingConnection",)


class RecordingCursor:
    rowcount = 0
    description = None

    def __init__(self):
        self.queries = []

    def execute(self, query, *args, **kwargs):
        self.queries.append(query)

    def fetchall(self, *args, **kwargs):
        return []

    def fetchone(self, *args, **kwargs):
        return None


class RecordingPGConn:
    server_version = 160000
    transaction_status = TransactionStatus.IDLE


class RecordingConnection:
    autocommit = False

    def __init__(self, **params):
        self.params = params
        self.pgconn = RecordingPGConn()
        self._cursor = RecordingCursor()

    def cursor(self, *args, **kwargs):
        return self._cursor

    def close(self):
        pass
