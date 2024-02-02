import typing as t


class BaseCache:
    def get(self, key: str) -> t.Any:
        raise NotImplementedError

    def set(self, key: str, value: t.Any, timeout: int | float) -> None:
        raise NotImplementedError

    update = set

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
