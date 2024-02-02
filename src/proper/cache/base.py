import typing as t


if t.TYPE_CHECKING:
    from proper import App


class BaseCache:
    """
    """
    def __init__(self, app: "App"):
        self.app = app

    def get(self, key: str) -> t.Any:
        raise NotImplementedError

    def set(self, key: str, value: t.Any, timeout: int | float) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def delete_expired(self) -> None:
        pass


class NoCache(BaseCache):
    def get(self, key: str) -> t.Any:
        pass

    def set(self, key: str, value: t.Any, timeout: int | float) -> None:
        pass

    def delete(self, key: str) -> None:
        pass
