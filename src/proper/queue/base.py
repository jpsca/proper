import typing as t

from huey.api import Huey


class BaseQueue(Huey):
    def dequeue(self, callback: t.Callable):  # type: ignore
        self.storage.dequeue(callback)  # type: ignore


class NoQueue(BaseQueue):
    def __init__(self, **kwargs):
        kwargs["immediate"] = True
        kwargs["immediate_use_memory"] = True
        super().__init__(**kwargs)
