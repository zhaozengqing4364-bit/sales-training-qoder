"""Unit tests for StepFun tool helper utilities."""

from __future__ import annotations

from sales_bot.websocket.components.stepfun_tool_helpers import (
    build_stepfun_tools_from_policy,
)


def test_build_tools_defaults_to_internal_retrieval_only():
    tools = build_stepfun_tools_from_policy({})

    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "search_internal_knowledge"
    properties = tools[0]["function"]["parameters"]["properties"]
    assert "metadata_filter" in properties
    assert properties["metadata_filter"]["type"] == "object"


def test_build_tools_kb_only_forces_internal_retrieval_even_if_misconfigured():
    tools = build_stepfun_tools_from_policy(
        {
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "enable_web_search": True,
                "enable_internal_retrieval": False,
                "retrieval_priority": "kb_only",
            },
        }
    )

    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "search_internal_knowledge"


def test_build_tools_enables_web_search_with_safe_options():
    tools = build_stepfun_tools_from_policy(
        {
            "tool_policy": {
                "enable_web_search": True,
                "network_access_mode": "controlled",
                "allow_web_search_without_kb": True,
                "web_search_top_k": 0,
                "web_search_timeout_seconds": -2,
            }
        }
    )

    assert len(tools) == 2
    assert tools[0]["type"] == "web_search"
    assert tools[0]["function"]["options"] == {
        "top_k": 1,
        "timeout_seconds": 1,
    }


def test_build_tools_handles_invalid_number_config_values():
    tools = build_stepfun_tools_from_policy(
        {
            "tool_policy": {
                "enable_web_search": True,
                "enable_internal_retrieval": False,
                "network_access_mode": "controlled",
                "allow_web_search_without_kb": True,
                "web_search_top_k": "oops",
                "web_search_timeout_seconds": None,
            }
        }
    )

    assert len(tools) == 1
    assert tools[0]["type"] == "web_search"
    assert tools[0]["function"]["options"] == {
        "top_k": 5,
        "timeout_seconds": 3,
    }


def test_build_tools_disables_web_search_when_internal_kb_is_bound():
    tools = build_stepfun_tools_from_policy(
        {
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "enable_web_search": True,
                "enable_internal_retrieval": True,
                "retrieval_priority": "balanced",
            },
        }
    )

    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "search_internal_knowledge"


def test_build_tools_disables_web_search_when_kb_bound_even_if_internal_disabled():
    tools = build_stepfun_tools_from_policy(
        {
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "enable_web_search": True,
                "enable_internal_retrieval": False,
                "retrieval_priority": "web_first",
            },
        }
    )

    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "search_internal_knowledge"


def test_build_tools_disables_web_search_when_network_access_mode_off():
    tools = build_stepfun_tools_from_policy(
        {
            "tool_policy": {
                "enable_web_search": True,
                "enable_internal_retrieval": False,
                "network_access_mode": "off",
                "allow_web_search_without_kb": True,
            }
        }
    )

    assert len(tools) == 0


def test_build_tools_allows_web_search_in_controlled_mode_without_kb():
    tools = build_stepfun_tools_from_policy(
        {
            "tool_policy": {
                "enable_web_search": True,
                "enable_internal_retrieval": False,
                "network_access_mode": "controlled",
                "allow_web_search_without_kb": True,
                "web_search_top_k": 3,
            }
        }
    )

    assert len(tools) == 1
    assert tools[0]["type"] == "web_search"
    assert tools[0]["function"]["options"]["top_k"] == 3


def test_build_tools_require_kb_grounding_forces_internal_retrieval():
    tools = build_stepfun_tools_from_policy(
        {
            "knowledge_base_ids": [],
            "tool_policy": {
                "enable_web_search": True,
                "enable_internal_retrieval": False,
                "network_access_mode": "controlled",
                "allow_web_search_without_kb": True,
                "retrieval_priority": "web_first",
                "require_kb_grounding": True,
            },
        }
    )

    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "search_internal_knowledge"
