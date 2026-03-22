"""Schemas for communication effectiveness snapshot and action card."""

from __future__ import annotations

from typing import Literal, TypedDict


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


OverallResult = Literal["pass", "strong_pass", "fail"]
