from __future__ import annotations

from fnmatch import fnmatch

import pytest

import launch_reset.cleaners.redis as redis_cleaner_module
from launch_reset.cleaners.redis import RedisCleaner
from launch_reset.errors import ResetSafetyError


class _ConnectionPool:
    def __init__(self, database: int) -> None:
        self.connection_kwargs = {"db": database}


class _FakeRedis:
    def __init__(self, keys: set[bytes], *, database: int) -> None:
        self.keys = keys
        self.connection_pool = _ConnectionPool(database)
        self.flushdb_calls = 0

    async def ping(self) -> bool:
        return True

    async def dbsize(self) -> int:
        return len(self.keys)

    async def scan_iter(self, *, match: str, count: int):
        del count
        for key in sorted(self.keys):
            if fnmatch(key.decode(), match):
                yield key

    async def delete(self, *keys: bytes) -> int:
        deleted = 0
        for key in keys:
            if key in self.keys:
                self.keys.remove(key)
                deleted += 1
        return deleted

    async def flushdb(self, *, asynchronous: bool) -> None:
        assert asynchronous is False
        self.flushdb_calls += 1
        self.keys.clear()

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_shared_redis_cleaner_deletes_only_confirmed_prefixes(
    monkeypatch,
) -> None:
    client = _FakeRedis(
        {b"sales-training:a", b"ws:session_state:1", b"foreign:key"},
        database=14,
    )
    monkeypatch.setattr(
        redis_cleaner_module, "redis_from_url", lambda *_a, **_k: client
    )
    cleaner = RedisCleaner(
        "redis://cache.internal:6379/14",
        {
            "database": 14,
            "mode": "shared_prefixes",
            "prefixes": ["sales-training:", "ws:session_state:"],
        },
    )

    result = await cleaner.apply()

    assert result == {"database": 14, "deleted_keys": 2, "clean": True}
    assert client.keys == {b"foreign:key"}
    assert client.flushdb_calls == 0


@pytest.mark.asyncio
async def test_exclusive_redis_cleaner_requires_database_allowlist(
    monkeypatch,
) -> None:
    client = _FakeRedis({b"project:a", b"foreign:key"}, database=14)
    monkeypatch.setattr(
        redis_cleaner_module, "redis_from_url", lambda *_a, **_k: client
    )
    cleaner = RedisCleaner(
        "redis://cache.internal:6379/14",
        {"database": 14, "mode": "exclusive_db", "prefixes": []},
    )

    with pytest.raises(ResetSafetyError, match="DATABASE_NOT_ALLOWLISTED"):
        await cleaner.apply()
    assert client.keys == {b"project:a", b"foreign:key"}

    monkeypatch.setenv("LAUNCH_RESET_ALLOWED_REDIS_DBS", "14")
    result = await cleaner.apply()
    assert result["deleted_keys"] == 2
    assert client.keys == set()
    assert client.flushdb_calls == 1


def test_redis_cleaner_rejects_wildcard_prefix_even_without_manifest_builder() -> None:
    with pytest.raises(ResetSafetyError, match="PREFIX_INVALID"):
        RedisCleaner(
            "redis://cache.internal:6379/14",
            {
                "database": 14,
                "mode": "shared_prefixes",
                "prefixes": ["sales-training:*"],
            },
        )
