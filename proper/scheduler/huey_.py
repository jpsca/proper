import sys
from typing import TYPE_CHECKING

import huey
import inflection
from huey.consumer import Consumer

from .base import BaseScheduler

if TYPE_CHECKING:
    from typing import Callable
    from proper import App


DEFAULT_HUEY_TYPE = "memory"


class HueyScheduler(BaseScheduler):
    running = False

    def __init__(self, app: "App", **config) -> None:
        self.app = app

        consumer_config = config.pop("consumer", {})
        huey_type = config.pop("type", DEFAULT_HUEY_TYPE)
        cls = f"{inflection.camelize(huey_type)}Huey"
        Cls = getattr(huey, cls)

        self.huey = Cls(**config)
        self.consumer = None
        if not config.get("inmediate", True):
            self.consumer = Consumer(self.huey, **consumer_config)

        self.pre_execute = self.huey.pre_execute
        self.post_execute = self.huey.post_execute
        self.pre_execute(app.db.engine.dispose)
        self.post_execute(app.db.s.remove)

        super().__init__(app, **config)

    def task(
        self,
        func: "Callable",
        retries: int = 0,
        **kwargs
    ) -> "Callable":
        kwargs["retries"] = retries
        return self.huey.task(func, **kwargs)

    def periodic_task(
        self,
        func: "Callable",
        validate_datetime: "Callable",
        retries=0,
        **kwargs
    ) -> "Callable":
        kwargs["retries"] = retries
        return self.huey.periodic_task(
            func,
            validate_datetime=validate_datetime,
            **kwargs,
        )

    def start(self) -> None:
        if self.running or not self.consumer:
            return

        if sys.version_info >= (3, 8) and sys.platform == "darwin":
            import multiprocessing

            try:
                multiprocessing.set_start_method("fork")
            except RuntimeError:
                pass
        self.consumer.start()
        self.running = True

    def shutdown(self, wait=True) -> None:
        if not self.running:
            return
        print("Stopping scheduler...")
        if wait:
            print("Waiting until all tasks finish...")
        if self.consumer:
            self.consumer.stop(graceful=wait)
        self.running = False
