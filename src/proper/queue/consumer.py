import typing as t

from huey.consumer import Consumer as HueyConsumer
from huey.consumer import Worker as HueyWorker

from .base import BaseQueue


class Worker(HueyWorker):
    def callback(self, data):
        task = self.huey.deserialize_task(data)
        self.delay = self.default_delay
        try:
            self.huey.execute(task)
        except Exception:
            self._logger.exception(
                "Unhandled error during execution of task %s.", task.id
            )

    def loop(self, *args, **kw):
        try:
            self.huey.dequeue(self.callback)
        except Exception:
            self._logger.exception("Error reading from queue")
        self.sleep()


class Consumer(HueyConsumer):
    worker_class = Worker

    def __init__(
        self,
        queue: BaseQueue,
        workers: int = 1,
        periodic: bool = True,
        initial_delay: int | float = 0.1,
        backoff: int | float = 1.15,
        max_delay: int | float = 10.0,
        scheduler_interval: int = 1,
        worker_type: t.Literal["thread"] | t.Literal["greenlet"] | t.Literal["process"] = "thread",
        check_worker_health: bool = True,
        health_check_interval: int = 10,
        flush_locks: bool = False,
        extra_locks: str = "",
    ):
        """
        Arguments:

            queue:
                Queue to use.
                This should be a subclass of `BaseQueue`.

            workers:
                Number of worker to spawn.

            periodic:
                Enable periodic task scheduler?

            initial_delay:
                Default queue polling interval.

            backoff:
                Exponential backoff factor when queue empty.

            max_delay:
                Maximum interval between polling events.

            scheduler_interval:
                Interval for the scheduler. Must be between 1 and 60s

            worker_type:
                Type of worker to use ("thread", "process", or "greenlet").

            check_worker_health:
                Whether to check worker health.

            health_check_interval:
                Interval for health checks.

            flush_locks:
                Whether to flush locks.

            extra_locks:
                Comma-separated extra locks to use.

        """
        super().__init__(
            queue,
            workers=workers,
            periodic=periodic,
            initial_delay=initial_delay,
            backoff=backoff,
            max_delay=max_delay,
            scheduler_interval=scheduler_interval,
            worker_type=worker_type,
            check_worker_health=check_worker_health,
            health_check_interval=health_check_interval,
            flush_locks=flush_locks,
            extra_locks=extra_locks,
        )
