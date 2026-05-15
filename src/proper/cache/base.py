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

    def set(self, key: str, value: t.Any, *, expires_in: int | None = None) -> None:
        raise NotImplementedError

    def get(self, key: str) -> t.Any:
        raise NotImplementedError

    update = set

    def get_or_set(
        self,
        key: str,
        default: t.Any,
        *,
        expires_in: int | None = None,
        race_condition_ttl: int | None = None,
    ) -> t.Any:
        value = self.get(key)
        if value is None:
            if callable(default):
                default = default()
            self.set(key, default, expires_in=expires_in)
            return default
        return value

    def increment(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        raise NotImplementedError

    def decrement(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        raise NotImplementedError

    def read_multi(self, *keys: str) -> dict[str, t.Any]:
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def write_multi(self, mapping: dict[str, t.Any], *, expires_in: int | None = None) -> None:
        for key, value in mapping.items():
            self.set(key, value, expires_in=expires_in)

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def delete_expired(self) -> None:
        pass

    def serialize(self, value: t.Any) -> bytes:
        return self.serializer.serialize(value)

    def deserialize(self, value: bytes) -> t.Any:
        return self.serializer.deserialize(value)


class NoCache(BaseCache):
    serializer_cls = NoSerializer

    def get(self, key: str) -> t.Any:
        pass

    def set(self, key: str, value: t.Any, *, expires_in: int | None = None) -> None:
        pass

    def increment(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        return 0

    def decrement(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        return 0

    def read_multi(self, *keys: str) -> dict[str, t.Any]:
        return {}

    def write_multi(self, mapping: dict[str, t.Any], *, expires_in: int | None = None) -> None:
        pass

    def delete(self, key: str) -> None:
        pass

    def clear(self) -> None:
        pass
