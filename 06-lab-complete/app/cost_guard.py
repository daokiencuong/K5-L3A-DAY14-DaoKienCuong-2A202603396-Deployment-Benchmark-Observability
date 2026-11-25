"""Daily token-cost budget stored in Redis and shared by all workers."""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


# Illustrative mock-LLM rates, USD per 1K tokens.
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _daily_key() -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"llm-cost:daily:{day}"


def check_budget() -> None:
    """Raise HTTP 402 before the LLM call when the daily budget is exhausted."""
    if r is None:
        raise HTTPException(status_code=503, detail="Cost guard storage is unavailable")
    try:
        used = float(r.get(_daily_key()) or 0.0)
    except (redis.RedisError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Cost guard storage is unavailable") from exc
    if used >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily LLM budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Add this request's estimated token cost to the UTC daily Redis counter."""
    if r is None:
        raise HTTPException(status_code=503, detail="Cost guard storage is unavailable")
    input_cost = max(0, input_tokens) * PRICE_INPUT_PER_1K / 1000
    output_cost = max(0, output_tokens) * PRICE_OUTPUT_PER_1K / 1000
    request_cost = input_cost + output_cost
    try:
        r.incrbyfloat(_daily_key(), request_cost)
        r.expire(_daily_key(), 60 * 60 * 24 * 2)
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail="Cost guard storage is unavailable") from exc
    return request_cost
