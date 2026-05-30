from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from curriculum_practice.services.roleplay.dual_read_observability import (
    record_dual_read_lookup,
    record_dual_read_mismatch,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)

DualReadMismatchHook = Callable[["DualReadCompareResult"], None]
SituationPackReadAuthority = Literal["phase_a", "phase_b1"]


@dataclass(frozen=True, slots=True)
class DualReadCompareResult:
    code: str
    phase_a_hash: str | None
    phase_b1_hash: str | None
    matched: bool


class DualReadSituationPackRepository(SituationPackRepository):
    """Migration-period repository that shadows Phase B1 against Phase A.

    When ``authority="phase_b1"`` (requires ``SITUATION_PACK_DUAL_READ`` and
    ``SITUATION_PACK_B1_AUTHORITY``), matched lookups serve the B1 projection.
    Hash mismatches are still logged for observability; Phase A remains the
    fallback on mismatch until dual-read is stable for at least two weeks.
    """

    def __init__(
        self,
        *,
        phase_a: SituationPackRepository,
        phase_b1: SituationPackRepository,
        authority: SituationPackReadAuthority = "phase_a",
        on_mismatch: DualReadMismatchHook | None = None,
    ) -> None:
        self._phase_a = phase_a
        self._phase_b1 = phase_b1
        self._authority = authority
        self._on_mismatch = on_mismatch
        self.mismatch_count = 0

    @property
    def authority(self) -> SituationPackReadAuthority:
        return self._authority

    def get_published(self, code: str) -> SituationPackDTO | None:
        phase_a_pack = self._phase_a.get_published(code)
        phase_b1_pack = self._phase_b1.get_published(code)
        matched = self._compare_code(
            code,
            phase_a_pack,
            phase_b1_pack,
            scope="lookup",
        ).matched
        return self._authoritative_pack(phase_a_pack, phase_b1_pack, matched=matched)

    def list_published(self) -> list[SituationPackDTO]:
        return self._reconcile_collection(
            "list_published",
            self._phase_a.list_published(),
            self._phase_b1.list_published(),
        )

    def get_any(self, code: str) -> SituationPackDTO | None:
        phase_a_pack = self._phase_a.get_any(code)
        phase_b1_pack = self._phase_b1.get_any(code)
        matched = self._compare_code(
            code,
            phase_a_pack,
            phase_b1_pack,
            scope="lookup",
        ).matched
        return self._authoritative_pack(phase_a_pack, phase_b1_pack, matched=matched)

    def list_all(self) -> list[SituationPackDTO]:
        return self._reconcile_collection(
            "list_all",
            self._phase_a.list_all(),
            self._phase_b1.list_all(),
        )

    def _reconcile_collection(
        self,
        scope: str,
        phase_a_items: list[SituationPackDTO],
        phase_b1_items: list[SituationPackDTO],
    ) -> list[SituationPackDTO]:
        phase_a_by_code = {item.code: item for item in phase_a_items}
        phase_b1_by_code = {item.code: item for item in phase_b1_items}
        reconciled: list[SituationPackDTO] = []
        for code in sorted(set(phase_a_by_code) | set(phase_b1_by_code)):
            phase_a_pack = phase_a_by_code.get(code)
            phase_b1_pack = phase_b1_by_code.get(code)
            matched = self._compare_code(
                code,
                phase_a_pack,
                phase_b1_pack,
                scope=scope,
            ).matched
            authoritative = self._authoritative_pack(
                phase_a_pack,
                phase_b1_pack,
                matched=matched,
            )
            if authoritative is not None:
                reconciled.append(authoritative)
        return reconciled

    def _authoritative_pack(
        self,
        phase_a_pack: SituationPackDTO | None,
        phase_b1_pack: SituationPackDTO | None,
        *,
        matched: bool,
    ) -> SituationPackDTO | None:
        if self._authority == "phase_b1" and matched and phase_b1_pack is not None:
            return phase_b1_pack
        return phase_a_pack

    def _compare_code(
        self,
        code: str,
        phase_a_pack: SituationPackDTO | None,
        phase_b1_pack: SituationPackDTO | None,
        *,
        scope: str,
    ) -> DualReadCompareResult:
        phase_a_hash = (
            situation_pack_content_hash(phase_a_pack) if phase_a_pack is not None else None
        )
        phase_b1_hash = (
            situation_pack_content_hash(phase_b1_pack)
            if phase_b1_pack is not None
            else None
        )
        matched = phase_a_hash == phase_b1_hash
        result = DualReadCompareResult(
            code=code,
            phase_a_hash=phase_a_hash,
            phase_b1_hash=phase_b1_hash,
            matched=matched,
        )
        record_dual_read_lookup(matched=matched)
        if not matched:
            self.mismatch_count += 1
            record_dual_read_mismatch(
                code=code,
                scope=scope,
                phase_a_hash=phase_a_hash,
                phase_b1_hash=phase_b1_hash,
            )
            if self._on_mismatch is not None:
                self._on_mismatch(result)
        return result
