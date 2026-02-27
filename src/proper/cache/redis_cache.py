import typing as t


try:
    import redis
except ImportError:
    redis = None  # type: ignore

from .base import BaseCache, SerializerProtocol


class RedisCache(BaseCache):
    """A Redis-backed cache."""

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        *,
        expires_in: int = 60 * 60 * 24 * 2,  # 2 days
        serializer: SerializerProtocol | None = None,
        **kwargs,
    ):
        if redis is None:
            raise ImportError(
                "redis is required to use the Redis cache backend. "
                "Install it with: pip install redis"
            )
        super().__init__(serializer=serializer)
        self.expires_in = expires_in
        self.client = redis.from_url(url, **kwargs)

    def set(self, key: str, value: t.Any, *, expires_in: int | None = None) -> None:
        data = self.serialize(value)
        ttl = expires_in if expires_in is not None else self.expires_in
        self.client.set(key, data, ex=ttl)

    def get(self, key: str) -> t.Any:
        data = self.client.get(key)
        if data is None:
            return None
        return self.deserialize(data)

    def get_or_set(
        self,
        key: str,
        default: t.Any,
        *,
        expires_in: int | None = None,
        race_condition_ttl: int | None = None,
    ) -> t.Any:
        if expires_in is None:
            expires_in = self.expires_in

        data = self.client.get(key)
        if data is not None:
            if not race_condition_ttl:
                return self.deserialize(data)
            remaining = self.client.ttl(key)
            if remaining < 0 or remaining > race_condition_ttl:
                return self.deserialize(data)
            # In race window — extend stale entry for other callers
            self.client.expire(key, race_condition_ttl)

        if callable(default):
            default = default()
        actual_ttl = expires_in + race_condition_ttl if race_condition_ttl else expires_in
        self.client.set(key, self.serialize(default), ex=actual_ttl)
        return default

    def increment(
        self, key: str, value: int = 1, *, expires_in: int | None = None
    ) -> int:
        ttl = expires_in if expires_in is not None else self.expires_in

        with self.client.pipeline() as pipe:
            pipe.incrby(key, value)
            pipe.expire(key, ttl)
            result, _ = pipe.execute()

        return result

    def decrement(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        return self.increment(key, -value, expires_in=expires_in)

    def read_multi(self, *keys: str) -> dict[str, t.Any]:
        values = self.client.mget(keys)
        result = {}
        for key, data in zip(keys, values, strict=False):
            if data is not None:
                result[key] = self.deserialize(data)
        return result

    def write_multi(
        self, mapping: dict[str, t.Any], *, expires_in: int | None = None
    ) -> None:
        ttl = expires_in if expires_in is not None else self.expires_in
        with self.client.pipeline() as pipe:
            for key, value in mapping.items():
                pipe.set(key, self.serialize(value), ex=ttl)
            pipe.execute()

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def clear(self) -> None:
        self.client.flushdb()

    def delete_expired(self) -> None:
        # Redis handles expiration automatically via TTL.
        pass

    def close(self) -> None:
        self.client.close()
