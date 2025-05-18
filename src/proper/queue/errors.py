from huey.exceptions import (
    CancelExecution,  # noqa
    ConfigurationError,  # noqa
    HueyException,  # noqa
    ResultTimeout,  # noqa
    RetryTask,  # noqa
    TaskException,  # noqa
    TaskLockedException,  # noqa
)


QueueException = HueyException

class ConsumerStopped(QueueException):
    pass
