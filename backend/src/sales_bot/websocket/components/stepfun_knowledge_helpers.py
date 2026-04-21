"""Compatibility imports for StepFun knowledge helper utilities.

The canonical implementation lives in ``common.knowledge.retrieval_helpers`` so
shared common services do not depend on the sales_bot package. Keep this module
as a stable import surface for existing StepFun code and tests.
"""

from __future__ import annotations

from common.knowledge.retrieval_helpers import *  # noqa: F401,F403
