"""
Disk-based cache (no Redis required).
Falls back to an in-memory dict if diskcache is not installed.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import structlog

from config.settings import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

_disk_cache = None
_mem_cache: dict = {}   # last-resort in-memory fallback


def _get_cache():
    global _disk_cache
    if _disk_cache is not None:
        return _disk_cache
    try:
        import diskcache
        cache_dir = os.path.join(os.path.dirname(__file__), "..", ".cache")
        _disk_cache = diskcache.Cache(cache_dir)
        return _disk_cache
    except ImportError:
        return None


def _key(namespace: str, identifier: str) -> str:
    h = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"recruitment:{namespace}:{h}"


def cache_get(namespace: str, identifier: str) -> Any | None:
    k = _key(namespace, identifier)
    dc = _get_cache()
    if dc:
        try:
            val = dc.get(k)
            if val is not None:
                return val
        except Exception:
            pass
    return _mem_cache.get(k)


def cache_set(namespace: str, identifier: str, value: Any, ttl: int | None = None) -> None:
    k = _key(namespace, identifier)
    ttl = ttl or 86400
    dc = _get_cache()
    if dc:
        try:
            dc.set(k, value, expire=ttl)
            return
        except Exception:
            pass
    _mem_cache[k] = value


def cached_github(username: str) -> Any | None:
    return cache_get("github", username)


def set_cached_github(username: str, data: dict) -> None:
    cache_set("github", username, data)


def cached_linkedin(url: str) -> Any | None:
    return cache_get("linkedin", url)


def set_cached_linkedin(url: str, data: dict) -> None:
    cache_set("linkedin", url, data)
