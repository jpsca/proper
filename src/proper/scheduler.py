import sys
import typing as t

import huey
from huey.consumer import Consumer


class HueyScheduler:
    running = False

    def __init__(self, **config) -> None:
        conns = config.get("SCHEDULER_CONNECTIONS", {})
        conn_name = config.get("SCHEDULER")
        conn_config = conns.get(conn_name, {"type": "MemoryHuey"})

        Cls = getattr(huey, conn_config.pop("type"))
        self.huey = Cls(**conn_config)

        self.consumer = None
        if not config.get("SCHEDULER_IMMEDIATE", True):
            consumer_config = config.get("SCHEDULER_CONSUMER", {})
            self.consumer = Consumer(self.huey, **consumer_config)

    @property
    def on_startup(self):
        return self.huey.on_startup

    @property
    def pre_execute(self):
        return self.huey.pre_execute

    @property
    def post_execute(self):
        return self.huey.post_execute

    def task(self, **kw) -> "t.Callable":
        return self.huey.task(**kw)

    def periodic_task(self, validate_datetime: "t.Callable", **kw) -> "t.Callable":
        return self.huey.periodic_task(validate_datetime=validate_datetime, **kw)

    def start(self) -> None:
        if self.running or not self.consumer:
            return

        if sys.platform == "darwin":
            import multiprocessing

            try:
                multiprocessing.set_start_method("fork")
            except RuntimeError:
                pass
        self.consumer.start()
        self.running = True

    def shutdown(self, wait: bool = True) -> None:
        if not self.running:
            return
        print("Stopping scheduler...")
        if wait:
            print("Waiting until all tasks finish...")
        if self.consumer:
            self.consumer.stop(graceful=wait)
        self.running = False
