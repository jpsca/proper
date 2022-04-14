from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Callable
    from proper import App


class BaseScheduler(ABC):
    def __init__(self, app: "App", **kw) -> None:
        app.on_dev_start(self.start)
        app.on_dev_shutdown(self.shutdown)

    @abstractmethod
    def task(self, func: "Callable") -> "Callable":
        pass

    def start(self) -> None:
        pass

    def shutdown(self) -> None:
        pass
