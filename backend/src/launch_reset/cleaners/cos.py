"""Tencent COS cleaner constrained to explicit project prefixes."""

from __future__ import annotations

from typing import Any

from common.cos.signing import get_cos_signing_service
from launch_reset.errors import ResetSafetyError


class CosPrefixCleaner:
    name = "cos"

    def __init__(self, scope: dict[str, Any]) -> None:
        self.scope = scope
        self.prefixes = tuple(str(prefix) for prefix in scope["prefixes"])
        if not self.prefixes:
            raise ResetSafetyError("[RESET_COS_PREFIXES_REQUIRED]")
        for prefix in self.prefixes:
            if not prefix or prefix.startswith("/") or not prefix.endswith("/"):
                raise ResetSafetyError("[RESET_COS_PREFIX_INVALID]")

    async def inspect(self) -> dict[str, Any]:
        signer = get_cos_signing_service()
        counts = {
            prefix: len(signer.list_object_keys(prefix)) for prefix in self.prefixes
        }
        return {
            "bucket": self.scope["bucket"],
            "region": self.scope["region"],
            "prefix_object_counts": counts,
        }

    async def apply(self) -> dict[str, Any]:
        signer = get_cos_signing_service()
        deleted = 0
        for prefix in self.prefixes:
            keys = signer.list_object_keys(prefix)
            signer.delete_object_keys(keys, prefix=prefix)
            deleted += len(keys)
        verification = await self.verify()
        if not verification["clean"]:
            raise ResetSafetyError("[RESET_COS_CLEAN_VERIFY_FAILED]")
        return {"deleted_objects": deleted, "clean": True}

    async def verify(self) -> dict[str, Any]:
        inspection = await self.inspect()
        clean = all(count == 0 for count in inspection["prefix_object_counts"].values())
        return {**inspection, "clean": clean}


__all__ = ["CosPrefixCleaner"]
