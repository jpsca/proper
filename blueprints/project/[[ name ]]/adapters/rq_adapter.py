from .redis_adapter import redis

from rq import Queue
from rq_scheduler import Scheduler


__all__ = ("QUEUES", "queue_default", "queue_notif", "scheduler")

queue_default = Queue("default", connection=redis)
queue_notif = Queue("notif", connection=redis)
QUEUES = [queue_default, queue_notif]

scheduler = Scheduler(connection=redis)
