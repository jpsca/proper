import pickle
import typing as t
from abc import abstractmethod


class SerializerProtocol(t.Protocol):
    @abstractmethod
    def serialize(self, value: t.Any) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def deserialize(self, value: bytes) -> t.Any:
        raise NotImplementedError


class NoSerializer:
    def serialize(self, value: t.Any) -> bytes:
        raise NotImplementedError

    def deserialize(self, value: bytes) -> t.Any:
        raise NotImplementedError


class Serializer:
    def __init__(self, protocol=pickle.HIGHEST_PROTOCOL):
        self.protocol = protocol or pickle.HIGHEST_PROTOCOL

    def serialize(self, value: t.Any) -> bytes:
        return pickle.dumps(value, self.protocol)

    def deserialize(self, value: bytes) -> t.Any:
        return pickle.loads(value)


class BaseCache:
    serializer_cls = Serializer

    def __init__(self, *, serializer: SerializerProtocol | None = None):
        if serializer is None:
            serializer = self.serializer_cls()
        self.serializer = serializer

    def set(self, key: str, value: t.Any, *, timestamp: int | None = None) -> None:
        raise NotImplementedError

    def get(self, key: str, *, expires_in: int | None = None) -> t.Any:
        raise NotImplementedError

    update = set

    def increment(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def delete_expired(self, expires_in: int | None = None) -> None:
        pass

    def serialize(self, value: t.Any) -> bytes:
        return self.serializer.serialize(value)

    def deserialize(self, value: bytes) -> t.Any:
        return self.serializer.deserialize(value)


class NoCache(BaseCache):
    serializer_cls = NoSerializer

    def get(self, key: str, *, expires_in: int | None = None) -> t.Any:
        pass

    def set(self, key: str, value: t.Any, *, timestamp: int | None = None) -> None:
        pass

    def increment(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        return 0

    def delete(self, key: str) -> None:
        pass
