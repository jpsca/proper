from .redis_adapter import redis

from rq import Queue, Retry


__all__ = ("QUEUES", "queue_default", "queue_notif")

queue_default = Queue("default", connection=redis)
queue_notif = Queue("notif", connection=redis)
QUEUES = [queue_default, queue_notif]

RETRY_ON_ERROR = Retry(max=4, interval=[1, 10, 30, 60])
