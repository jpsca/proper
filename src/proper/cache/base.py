import pickle
import typing as t


class Serializer:
    def __init__(self, protocol=pickle.HIGHEST_PROTOCOL):
        self.protocol = protocol or pickle.HIGHEST_PROTOCOL

    def serialize(self, value: t.Any) -> bytes:
        return pickle.dumps(value, self.protocol)

    def deserialize(self, value: bytes) -> t.Any:
        return pickle.loads(value)


class BaseCache:
    serializer_cls = Serializer

    def __init__(self, serializer_cls: type[Serializer] | None):
        Serializer = serializer_cls or self.serializer_cls
        self.serializer = Serializer()

    def get(self, key: str) -> t.Any:
        raise NotImplementedError

    def set(self, key: str, value: t.Any, timeout: int) -> None:
        raise NotImplementedError

    update = set

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def delete_expired(self) -> None:
        pass

    def serialize(self, value: t.Any) -> bytes:
        return self.serializer.serialize(value)

    def deserialize(self, value: bytes) -> t.Any:
        return self.serializer.deserialize(value)


class NoCache(BaseCache):
    def get(self, key: str) -> t.Any:
        pass

    def set(self, key: str, value: t.Any, timeout: int | float) -> None:
        pass

    def delete(self, key: str) -> None:
        pass
