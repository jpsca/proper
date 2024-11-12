import typing as t

from huey.api import Result, ResultGroup

from .base import BaseQueue
from .consumer import Consumer
from .solid_storage import SolidStorage


SIGNAL_CREATED = "created"


class SolidQueue(BaseQueue):
    storage_class = SolidStorage

    def enqueue(self, task):
        if task.expires:
            task.resolve_expires(self.utc)

        if self._immediate:
            self.execute(task)
        else:
            self.storage.enqueue(task, self.serialize_task(task))
            self._emit(SIGNAL_CREATED, task)

        if not self.results:
            return

        if task.on_complete:
            current = task
            results = []
            while current is not None:
                results.append(Result(self, current))
                current = current.on_complete
            return ResultGroup(results)
        else:
            return Result(self, task)

    def dequeue(self, callback: t.Callable):  # type: ignore
        self.storage.dequeue(callback)  # type: ignore

    def create_consumer(self, **options):
        return Consumer(self, **options)
