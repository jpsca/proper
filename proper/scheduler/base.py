from abc import ABC, abstractmethod


class BaseScheduler(ABC):
    def __init__(self, app):
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
