from .redis_adapter import redis

from rq import Queue


__all__ = ("QUEUES", "queue_default", "queue_notif")

queue_default = Queue("default", connection=redis)
queue_notif = Queue("notif", connection=redis)
QUEUES = [queue_default, queue_notif]
