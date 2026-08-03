"""Redis cleaner constrained to one database or explicit key prefixes."""

from __future__ import annotations

import os
from typing import Any

from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from launch_reset.errors import ResetSafetyError


class RedisCleaner:
    name = "redis"

    def __init__(self, raw_url: str, scope: dict[str, Any]) -> None:
        self.raw_url = raw_url
        self.scope = scope
        self.database = int(scope["database"])
        self.mode = str(scope["mode"])
        self.prefixes = tuple(str(prefix) for prefix in scope.get("prefixes", []))
        if self.mode not in {"exclusive_db", "shared_prefixes"}:
            raise ResetSafetyError("[RESET_REDIS_MODE_INVALID]")
        if self.mode == "shared_prefixes" and not self.prefixes:
            raise ResetSafetyError("[RESET_REDIS_SHARED_PREFIXES_REQUIRED]")
        if any(
            not prefix or any(character in prefix for character in "*?[]")
            for prefix in self.prefixes
        ):
            raise ResetSafetyError("[RESET_REDIS_PREFIX_INVALID]")

    async def _client(self) -> Redis:
        client = redis_from_url(self.raw_url, decode_responses=False)
        await client.ping()
        actual_db = int(client.connection_pool.connection_kwargs.get("db", 0))
        if actual_db != self.database:
            await client.aclose()
            raise ResetSafetyError("[RESET_REDIS_DATABASE_MISMATCH]")
        return client

    async def _count_prefix(self, client: Redis, prefix: str) -> int:
        count = 0
        async for _key in client.scan_iter(match=f"{prefix}*", count=500):
            count += 1
        return count

    async def inspect(self) -> dict[str, Any]:
        client = await self._client()
        try:
            database_size = int(await client.dbsize())
            prefix_counts = {
                prefix: await self._count_prefix(client, prefix)
                for prefix in self.prefixes
            }
        finally:
            await client.aclose()
        return {
            "database": self.database,
            "mode": self.mode,
            "database_key_count": database_size,
            "prefix_key_counts": prefix_counts,
        }

    async def apply(self) -> dict[str, Any]:
        client = await self._client()
        deleted = 0
        try:
            if self.mode == "exclusive_db":
                allowed_databases = {
                    int(value.strip())
                    for value in os.getenv("LAUNCH_RESET_ALLOWED_REDIS_DBS", "").split(
                        ","
                    )
                    if value.strip().isdigit()
                }
                if self.database not in allowed_databases:
                    raise ResetSafetyError("[RESET_REDIS_DATABASE_NOT_ALLOWLISTED]")
                deleted = int(await client.dbsize())
                await client.flushdb(asynchronous=False)
            else:
                for prefix in self.prefixes:
                    batch: list[bytes] = []
                    async for key in client.scan_iter(match=f"{prefix}*", count=500):
                        batch.append(key)
                        if len(batch) >= 500:
                            deleted += int(await client.delete(*batch))
                            batch.clear()
                    if batch:
                        deleted += int(await client.delete(*batch))
        finally:
            await client.aclose()
        verification = await self.verify()
        if not verification["clean"]:
            raise ResetSafetyError("[RESET_REDIS_CLEAN_VERIFY_FAILED]")
        return {"database": self.database, "deleted_keys": deleted, "clean": True}

    async def verify(self) -> dict[str, Any]:
        inspection = await self.inspect()
        clean = (
            inspection["database_key_count"] == 0
            if self.mode == "exclusive_db"
            else all(count == 0 for count in inspection["prefix_key_counts"].values())
        )
        return {**inspection, "clean": clean}


__all__ = ["RedisCleaner"]
