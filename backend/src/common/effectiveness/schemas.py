"""Schemas for communication effectiveness snapshot and action card."""

from __future__ import annotations

from typing import Literal, TypedDict


SalesStageKey = Literal["discovery", "objection", "closing"]
SalesCoachingFocusType = Literal[
    "value_translation_gap",
    "evidence_gap",
    "objection_handling_gap",
    "next_step_gap",
]
SalesCoachingDimension = Literal[
    "价值表达",
    "客户收益连接",
    "证据使用",
    "异议处理",
    "推进下一步",
]


class PassFlags(TypedDict):
    pass_3min_flow: bool
    pass_5turn_defense: bool
    pass_4step_structure: bool


class NextGoal(TypedDict):
    goal_type: str
    goal_text: str
    rule: str


class ActionCard(TypedDict):
    issue: str
    replacement: str
    next_turn_rule: str


class SalesStageContext(TypedDict, total=False):
    current_stage: str
    stage_name: str
    key_actions: list[str]
    guidance: str
    progress: float


class SalesScoreDimension(TypedDict, total=False):
    name: str
    score: float
    delta: float
    trend: str


class SalesScoreContext(TypedDict, total=False):
    overall_score: float
    feedback: str
    suggestions: list[str]
    stage_name: str
    dimension_scores: dict[str, float]
    dimensions: list[SalesScoreDimension]


class SalesCoachingFocus(TypedDict):
    issue: str
    replacement: str
    next_turn_rule: str


OverallResult = Literal["pass", "strong_pass", "fail"]
