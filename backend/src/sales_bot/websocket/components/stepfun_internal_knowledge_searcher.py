"""Compatibility imports for StepFun internal knowledge search orchestration.

The canonical implementation lives in ``common.knowledge.internal_searcher`` so
common KB-lock enforcement can reuse it without a reverse dependency on
sales_bot. Keep this module as a stable import surface for existing StepFun
code and tests.
"""

from __future__ import annotations

from common.knowledge.internal_searcher import *  # noqa: F401,F403
