import sys

import huey
import inflection
from huey.consumer import Consumer

from proper.scheduler import BaseScheduler
from ..app import app, config


DEFAULT_HUEY_TYPE = "sqlite"


class HueyScheduler(BaseScheduler):
    running = False

    def __init__(self, app, **config):
        self.app = app

        consumer_config = config.pop("consumer", {})
        huey_type = config.pop("type", DEFAULT_HUEY_TYPE)
        cls = f"{inflection.camelize(huey_type)}Huey"
        Cls = getattr(huey, cls)

        self.huey = Cls(**config)
        self.pre_execute = self.huey.pre_execute
        self.post_execute = self.huey.post_execute
        self.consumer = Consumer(self.huey, **consumer_config)

        super().__init__(app, **config)

    def task(self, func, retries=0, **kwargs):
        return self.huey.task(func, retries=retries, **kwargs)

    def periodic_task(self, func, validate_datetime, retries=0, **kwargs):
        return self.huey.periodic_task(
            func,
            validate_datetime=validate_datetime,
            retries=retries,
            **kwargs,
        )

    def start(self):
        if self.running:
            return

        if sys.version_info >= (3, 8) and sys.platform == "darwin":
            import multiprocessing

            try:
                multiprocessing.set_start_method("fork")
            except RuntimeError:
                pass
        self.consumer.start()
        self.running = True

    def shutdown(self, wait=True):
        if not self.running:
            return
        print("Stopping scheduler...")
        if wait:
            print("Waiting until all tasks finish...")
        self.consumer.stop(graceful=wait)
        self.running = False


scheduler = HueyScheduler(app, **config.scheduler)
app.scheduler = scheduler


@scheduler.pre_execute()
def db_engine_dispose():
    app.db.engine.dispose()


@scheduler.post_execute()
def db_session_remove():
    app.db.s.remove()
