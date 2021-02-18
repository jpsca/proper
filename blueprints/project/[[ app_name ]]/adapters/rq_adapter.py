from rq import Queue, Retry

from ..config import config
from .redis_adapter import redis


__all__ = (
    "QUEUES",
    "queue_default",
    "queue_notif",
    "RETRY_ON_ERROR",
    "DEFAULT_JOB_OPTIONS",
)

queue_default = Queue("default", connection=redis)
queue_notif = Queue("notif", connection=redis)
QUEUES = [queue_default, queue_notif]

RETRY_ON_ERROR = Retry(max=4, interval=[1, 10, 30, 60])

DEFAULT_JOB_OPTIONS = {
    "retry": RETRY_ON_ERROR,
    "ttl": 7 * 24 * 3600,  # max time on a queue
    "result_ttl": 0,
    "failure_ttl": 600 if config.debug else 0,
}
