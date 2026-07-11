"""Neutral Roleplay Contract and Situation Pack bounded context."""

from roleplay.compiler import (
    RoleplayCompileFailure,
    RoleplayContractCompileError,
    RoleplayContractCompiler,
    RoleplayGateResult,
    build_roleplay_turn_context,
    initial_roleplay_disclosure_state,
    normalize_roleplay_disclosure_state,
    resolve_roleplay_disclosure_state,
    roleplay_readiness_from_contract,
    visible_case_payload,
)
from roleplay.contracts import (
    LEGACY_ROLEPLAY_STATUS,
    ROLEPLAY_COMPLIANCE_METRICS_KEY,
    ROLEPLAY_CONTRACT_COMPILER_VERSION,
    ROLEPLAY_CONTRACT_SCHEMA_VERSION,
    ROLEPLAY_DISCLOSURE_STATE_KEY,
    ROLEPLAY_STAGE_AUTHORITY,
    RoleplayComplianceDecision,
    check_roleplay_output,
    roleplay_audit_hash,
    roleplay_contract_hash,
)
from roleplay.situation_packs import (
    SituationPackPort,
    SituationPackSnapshot,
    situation_pack_content_hash,
)

__all__ = [
    "LEGACY_ROLEPLAY_STATUS",
    "ROLEPLAY_COMPLIANCE_METRICS_KEY",
    "ROLEPLAY_CONTRACT_COMPILER_VERSION",
    "ROLEPLAY_CONTRACT_SCHEMA_VERSION",
    "ROLEPLAY_DISCLOSURE_STATE_KEY",
    "ROLEPLAY_STAGE_AUTHORITY",
    "RoleplayComplianceDecision",
    "RoleplayCompileFailure",
    "RoleplayContractCompileError",
    "RoleplayContractCompiler",
    "RoleplayGateResult",
    "SituationPackPort",
    "SituationPackSnapshot",
    "check_roleplay_output",
    "build_roleplay_turn_context",
    "initial_roleplay_disclosure_state",
    "normalize_roleplay_disclosure_state",
    "resolve_roleplay_disclosure_state",
    "roleplay_audit_hash",
    "roleplay_contract_hash",
    "roleplay_readiness_from_contract",
    "situation_pack_content_hash",
    "visible_case_payload",
]
