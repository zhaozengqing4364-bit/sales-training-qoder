from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from common.db.schemas import SessionCreate
from common.db.session_lifecycle import SessionLifecycleTransition


class PracticeSessionPortError(Exception):
    def __init__(
        self,
        error_code: str,
        *,
        status_code: int = 400,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message
        self.details = details


class RuntimePolicyResolver(Protocol):
    async def resolve_effective_policy(
        self,
        *,
        agent_id: str | None,
        persona_id: str | None,
        voice_mode_override: str | None,
        runtime_profile_override: str | None,
    ) -> dict[str, Any]: ...


@dataclass(slots=True)
class PracticeTemplateRuntimeIdentity:
    agent_id: str
    persona_id: str
    runtime_profile_id: str
    voice_mode: str | None


@dataclass(slots=True)
class PracticeSessionCreateContext:
    session_data: SessionCreate
    current_user: User
    requested_scenario: Scenario | None
    agent_id_str: str | None
    persona_id_str: str | None
    session_policy_snapshot: dict[str, Any]
    effective_voice_policy: dict[str, Any]


@dataclass(slots=True)
class PracticeSessionTerminalContext:
    session_id: str
    session: PracticeSession
    scenario_type: str
    transition: SessionLifecycleTransition


@dataclass(slots=True)
class PracticeSessionTerminalResult:
    session: PracticeSession
    snapshot: dict[str, Any] | None
    summary: Any | None = None


RuntimePolicyResolverFactory = Callable[[AsyncSession], RuntimePolicyResolver]
RuntimeDescriptorBuilder = Callable[
    [PracticeSession, str | None],
    Any,
]
PracticeTemplateRuntimeIdentityResolver = Callable[
    [AsyncSession, SessionCreate, str, str | None, str | None],
    Awaitable[PracticeTemplateRuntimeIdentity | None],
]
PracticeSessionSnapshotApplier = Callable[
    [AsyncSession, PracticeSession, SessionCreate, str, User],
    Awaitable[None],
]
AgentPersonaPairValidator = Callable[
    [AsyncSession, str | None, str | None],
    Awaitable[dict[str, Any] | None],
]
PracticeSessionCreator = Callable[
    [AsyncSession, PracticeSessionCreateContext],
    Awaitable[PracticeSession],
]
PracticeSessionTerminalHandler = Callable[
    [AsyncSession, PracticeSessionTerminalContext],
    Awaitable[PracticeSessionTerminalResult],
]

_runtime_policy_resolver_factory: RuntimePolicyResolverFactory | None = None
_runtime_descriptor_builder: RuntimeDescriptorBuilder | None = None
_template_runtime_identity_resolver: PracticeTemplateRuntimeIdentityResolver | None = None
_session_snapshot_applier: PracticeSessionSnapshotApplier | None = None
_agent_persona_pair_validator: AgentPersonaPairValidator | None = None
_session_creators: dict[str, PracticeSessionCreator] = {}
_terminal_handlers: dict[str, PracticeSessionTerminalHandler] = {}


def register_runtime_policy_resolver_factory(
    factory: RuntimePolicyResolverFactory,
) -> None:
    global _runtime_policy_resolver_factory
    _runtime_policy_resolver_factory = factory


def get_runtime_policy_resolver(db: AsyncSession) -> RuntimePolicyResolver:
    if _runtime_policy_resolver_factory is None:
        raise PracticeSessionPortError(
            "[RUNTIME_POLICY_RESOLVER_NOT_REGISTERED]",
            status_code=500,
        )
    return _runtime_policy_resolver_factory(db)


def register_runtime_descriptor_builder(builder: RuntimeDescriptorBuilder) -> None:
    global _runtime_descriptor_builder
    _runtime_descriptor_builder = builder


def build_registered_runtime_descriptor(
    session: PracticeSession,
    *,
    scenario_type: str | None,
) -> Any | None:
    if _runtime_descriptor_builder is None:
        return None
    return _runtime_descriptor_builder(session, scenario_type)


def register_practice_template_runtime_identity_resolver(
    resolver: PracticeTemplateRuntimeIdentityResolver,
) -> None:
    global _template_runtime_identity_resolver
    _template_runtime_identity_resolver = resolver


async def resolve_registered_practice_template_runtime_identity(
    db: AsyncSession,
    *,
    session_data: SessionCreate,
    scenario_type_value: str,
    requested_agent_id: str | None,
    requested_persona_id: str | None,
) -> PracticeTemplateRuntimeIdentity | None:
    if _template_runtime_identity_resolver is None:
        if session_data.practice_template_id is None:
            return None
        raise PracticeSessionPortError(
            "[PRACTICE_TEMPLATE_RESOLVER_NOT_REGISTERED]",
            status_code=500,
        )
    return await _template_runtime_identity_resolver(
        db,
        session_data,
        scenario_type_value,
        requested_agent_id,
        requested_persona_id,
    )


def register_practice_session_snapshot_applier(
    applier: PracticeSessionSnapshotApplier,
) -> None:
    global _session_snapshot_applier
    _session_snapshot_applier = applier


async def apply_registered_practice_session_snapshot(
    db: AsyncSession,
    *,
    session: PracticeSession,
    session_data: SessionCreate,
    scenario_type_value: str,
    current_user: User,
) -> None:
    if session_data.practice_template_id is None:
        return
    if _session_snapshot_applier is None:
        raise PracticeSessionPortError(
            "[PRACTICE_TEMPLATE_SNAPSHOT_APPLIER_NOT_REGISTERED]",
            status_code=500,
        )
    await _session_snapshot_applier(
        db,
        session,
        session_data,
        scenario_type_value,
        current_user,
    )


def register_agent_persona_pair_validator(
    validator: AgentPersonaPairValidator,
) -> None:
    global _agent_persona_pair_validator
    _agent_persona_pair_validator = validator


async def validate_registered_agent_persona_pair(
    db: AsyncSession,
    *,
    agent_id_str: str | None,
    persona_id_str: str | None,
) -> dict[str, Any] | None:
    if not (agent_id_str and persona_id_str):
        return None
    if _agent_persona_pair_validator is None:
        raise PracticeSessionPortError(
            "[AGENT_PERSONA_VALIDATOR_NOT_REGISTERED]",
            status_code=500,
        )
    return await _agent_persona_pair_validator(db, agent_id_str, persona_id_str)


def register_practice_session_creator(
    scenario_type: str,
    creator: PracticeSessionCreator,
) -> None:
    _session_creators[scenario_type] = creator


def get_practice_session_creator(scenario_type: str) -> PracticeSessionCreator | None:
    return _session_creators.get(scenario_type)


def register_practice_session_terminal_handler(
    scenario_type: str,
    handler: PracticeSessionTerminalHandler,
) -> None:
    _terminal_handlers[scenario_type] = handler


def get_practice_session_terminal_handler(
    scenario_type: str,
) -> PracticeSessionTerminalHandler | None:
    return _terminal_handlers.get(scenario_type)


def clear_practice_session_contributors() -> None:
    global _runtime_policy_resolver_factory
    global _runtime_descriptor_builder
    global _template_runtime_identity_resolver
    global _session_snapshot_applier
    global _agent_persona_pair_validator
    _runtime_policy_resolver_factory = None
    _runtime_descriptor_builder = None
    _template_runtime_identity_resolver = None
    _session_snapshot_applier = None
    _agent_persona_pair_validator = None
    _session_creators.clear()
    _terminal_handlers.clear()
