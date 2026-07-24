"""Distributed brute-force protection backed by Redis."""

import hashlib

import redis

from .config import settings

_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _identifier(ip: str) -> str:
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def is_blocked(ip: str, username: str) -> bool:
    del username
    return bool(_redis.exists(f"mailctl:login:block:{_identifier(ip)}"))


def register_failure(ip: str, username: str) -> int:
    del username
    identifier = _identifier(ip)
    attempts_key = f"mailctl:login:attempts:{identifier}"
    block_key = f"mailctl:login:block:{identifier}"
    attempts = _redis.incr(attempts_key)
    if attempts == 1:
        _redis.expire(attempts_key, settings.LOGIN_BLOCK_SECONDS)
    if attempts >= settings.LOGIN_MAX_FAILURES:
        pipe = _redis.pipeline()
        pipe.setex(block_key, settings.LOGIN_BLOCK_SECONDS, "1")
        pipe.delete(attempts_key)
        pipe.execute()
    return attempts


def clear_failures(ip: str, username: str) -> None:
    del username
    identifier = _identifier(ip)
    _redis.delete(
        f"mailctl:login:attempts:{identifier}",
        f"mailctl:login:block:{identifier}",
    )
