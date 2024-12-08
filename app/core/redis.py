import redis.asyncio as redis

from app.core.config import settings


class RedisConnectionManager:
    def __init__(self):
        self._pool = redis.ConnectionPool.from_url(settings.REDIS_URI)

    def get_connection(self):
        return redis.Redis(connection_pool=self._pool)


manager = RedisConnectionManager()
