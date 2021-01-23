from redis import Redis

from ..config import config


__all__ = ("redis", )

redis = Redis(host=config.redis.host, port=config.redis.port, db=config.redis.db)
