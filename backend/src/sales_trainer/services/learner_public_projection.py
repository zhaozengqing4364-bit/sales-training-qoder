from __future__ import annotations

from typing import Any, Final

LEARNER_INTERNAL_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "raw_model_output",
        "validated_output",
        "interaction_snapshot",
        "public_interaction_raw",
        "prompt_template_id",
        "prompt_revision_id",
        "prompt_contract_hash",
        "scoring_prompt_template_id",
        "scoring_prompt_revision_id",
        "scoring_contract_hash",
        "trace_id",
        "article_snapshot",
        "path_config_snapshot",
        "config_snapshot",
        "source_evidence",
        "answer_key",
        "answer_keys",
        "correct_answer",
        "correct_answers",
        "scoring_rubric",
        "rubric",
        "rubrics",
        "next_question",
    }
)


def find_learner_internal_fields(
    payload: Any,
    *,
    public_subtrees: frozenset[str] = frozenset(),
) -> list[str]:
    leaked: list[str] = []
    stack: list[Any] = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key in LEARNER_INTERNAL_FIELD_NAMES:
                    leaked.append(str(key))
                if key in public_subtrees:
                    continue
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    stack.append(item)
    return sorted(set(leaked))


def strip_learner_internal_fields(
    payload: Any,
    *,
    public_subtrees: frozenset[str] = frozenset(),
) -> Any:
    if isinstance(payload, dict):
        changed = False
        stripped: dict[str, Any] = {}
        for key, value in payload.items():
            if key in LEARNER_INTERNAL_FIELD_NAMES:
                changed = True
                continue
            if key in public_subtrees:
                stripped[key] = value
                continue
            safe_value = strip_learner_internal_fields(
                value,
                public_subtrees=public_subtrees,
            )
            changed = changed or safe_value is not value
            stripped[key] = safe_value
        return stripped if changed else payload
    if isinstance(payload, list):
        changed = False
        stripped_items: list[Any] = []
        for item in payload:
            safe_item = strip_learner_internal_fields(
                item,
                public_subtrees=public_subtrees,
            )
            changed = changed or safe_item is not item
            stripped_items.append(safe_item)
        return stripped_items if changed else payload
    return payload


def assert_learner_public_payload(
    payload: dict[str, Any],
    *,
    public_subtrees: frozenset[str] = frozenset(),
) -> None:
    leaked = find_learner_internal_fields(payload, public_subtrees=public_subtrees)
    if leaked:
        raise RuntimeError(f"learner payload leaked internal fields: {leaked}")
