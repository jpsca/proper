from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Callable
    from proper import App


class Scheduler:
    def __init__(self, app: "App", **kw) -> None:
        app.on_dev_start(self.start)
        app.on_dev_shutdown(self.shutdown)

    # Implement this method in concrete subclasses
    def task(self, **kw) -> "Callable":
        raise NotImplementedError

    def start(self) -> None:
        pass

    def shutdown(self) -> None:
        pass
