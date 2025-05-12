import typing as t

from huey.storage import BaseStorage as HueyStorage


class BaseStorage(HueyStorage):
    def check_conn(self):
        """
        Check the connection to the storage backend.
        Implement in the subclass if needed
        """
        pass

    def dequeue(self, callback: t.Callable | None = None):
        return super().dequeue()
