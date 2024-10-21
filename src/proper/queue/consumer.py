from huey.consumer import Consumer as HueyConsumer
from huey.consumer import Worker as HueyWorker


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
