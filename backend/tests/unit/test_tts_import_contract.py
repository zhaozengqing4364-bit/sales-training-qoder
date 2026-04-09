import importlib
import sys

import pytest



def test_importing_tts_service_does_not_require_edge_tts_binary_stack() -> None:
    sys.modules.pop("common.audio.tts_service", None)

    try:
        module = importlib.import_module("common.audio.tts_service")
    except Exception as exc:  # pragma: no cover - exercised when the regression is present
        pytest.fail(f"unexpected import failure: {exc}")

    assert hasattr(module, "get_tts_service")
