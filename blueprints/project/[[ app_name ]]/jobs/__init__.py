from rq import Retry

from ..adapters import redis
from ..config import config


QUEUES = ["default"]

RETRY_ON_ERROR = Retry(max=4, interval=[1, 10, 30, 60])

DEFAULT_JOB_OPTIONS = {
    "connection": redis,
    "retry": RETRY_ON_ERROR,
    "ttl": 7 * 24 * 3600,  # max time on a queue
    "result_ttl": 0,
    "failure_ttl": 600 if config.debug else 0,
}
