"""Atomic Redis sliding-window rate limiter shared by all workers."""
import hashlib
import math
import time

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


_WINDOW_MS = 60_000
_CHECK_AND_ADD = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = window
  if oldest[2] then retry = math.max(1, tonumber(oldest[2]) + window - now) end
  return {0, retry}
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('PEXPIRE', key, window)
return {1, 0}
"""


def check_rate_limit(key: str) -> None:
    """Allow at most RATE_LIMIT_PER_MINUTE requests per key in 60 seconds."""
    if r is None:
        raise HTTPException(status_code=503, detail="Rate limiting storage is unavailable")
    now_ms = time.time_ns() // 1_000_000
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    member = f"{now_ms}:{time.time_ns()}"
    try:
        allowed, retry_ms = r.eval(
            _CHECK_AND_ADD,
            1,
            f"rate-limit:{digest}",
            now_ms,
            _WINDOW_MS,
            max(1, settings.rate_limit_per_minute),
            member,
        )
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiting storage is unavailable") from exc
    if int(allowed) != 1:
        retry_after = max(1, math.ceil(int(retry_ms) / 1000))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
