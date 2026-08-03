from __future__ import annotations

import inspect

from sales_trainer.orchestration.activities.assignment import AssignmentActivityHandler


def test_legacy_assignment_handler_exposes_projection_only() -> None:
    """Foundation assignment writes belong to the v2 audio-assessment runtime."""

    parameters = inspect.signature(AssignmentActivityHandler).parameters

    assert "storage" not in parameters
    assert "submit" not in {
        name
        for name, member in inspect.getmembers(
            AssignmentActivityHandler,
            inspect.isfunction,
        )
    }
