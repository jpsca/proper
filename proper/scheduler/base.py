__all__ = ("BaseScheduler", )


class BaseScheduler:
    @property
    def running(self):
        return False

    def __init__(self, config):
        pass

    def task(self, func, retries=0, retry_delay=0, **kwargs):
        pass

    def periodic_task(self, func, validate_datetime, retries=0, retry_delay=0, **kwargs):
        pass

    def start(self):
        pass

    def shutdown(self, wait=True):
        pass
