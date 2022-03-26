from abc import ABC, abstractmethod


__all__ = ("BaseScheduler", "DummyScheduler")


class BaseScheduler(ABC):
    def __init__(self, app, **config):
        app.on_dev_start(self.start)
        app.on_dev_shutdown(self.shutdown)

    @abstractmethod
    def task(self, func, *args, **kwargs):
        pass

    @abstractmethod
    def periodic_task(self, func, *args, **kwargs):
        pass

    def start(self):
        pass

    def shutdown(self, wait=True):
        pass


class DummyScheduler(BaseScheduler):
    def __init__(self, app, **config):
        pass

    def task(self, *args, **kwargs):
        raise NotImplementedError

    def periodic_task(self, *args, **kwargs):
        raise NotImplementedError
