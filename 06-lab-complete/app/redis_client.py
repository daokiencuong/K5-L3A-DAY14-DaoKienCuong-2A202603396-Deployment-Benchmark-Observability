"""Lazy Redis connection shared by rate limiting, budget guard and readiness."""
import redis

from app.config import settings


# Constructing a Redis client does not open a connection. The app can therefore
# start during a Redis outage; individual operations and /ready report failure.
r = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1.5,
    socket_timeout=2.0,
) if settings.redis_url else None


def redis_healthy() -> bool:
    if r is None:
        return False
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
