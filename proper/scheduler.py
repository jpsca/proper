from apscheduler.schedulers.background import BackgroundScheduler


class Scheduler:
    @property
    def running(self):
        return self._scheduler.running

    def __init__(self):
        self._scheduler = BackgroundScheduler()

    def start(self):
        if (not self._scheduler.running):
            self._scheduler.start()
            print("Scheduler has started")

    def shutdown(self, wait=True):
        if (self._scheduler.running):
            print("Waiting for the background tasks to complete...")
            self._scheduler.shutdown(wait)

    def add_task(self, func, **opts):
        return self._scheduler.add_job(func, **opts)
