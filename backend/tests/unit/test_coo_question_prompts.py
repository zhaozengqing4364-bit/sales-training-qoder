import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from coo_question_prompts import (  # noqa: E402
    load_short_answer_prompts,
    resolve_short_answer_ai_scoring,
)


def test_load_short_answer_prompts_includes_series_and_default() -> None:
    data = load_short_answer_prompts()
    assert "default" in data
    assert "series" in data
    assert "1" in data["series"]
    assert "{stem}" in data["default"]["prompt_template"]
    assert "{reference_answer}" in data["default"]["prompt_template"]
    assert "{answer}" in data["default"]["prompt_template"]


def test_resolve_short_answer_ai_scoring_uses_series_prompt() -> None:
    spec = {
        "series_index": 1,
        "natural_key": "coo-series-01-q3",
        "question_type": "short_answer",
    }
    config = resolve_short_answer_ai_scoring(spec)
    assert config["enabled"] is True
    assert config["pass_threshold"] == 70
    assert "COO 市场训练阅卷助教" in config["system_prompt"]
    assert "系列之1" in config["prompt_template"]
    assert "{stem}" in config["prompt_template"]
    assert "{reference_answer}" in config["prompt_template"]
    assert "{answer}" in config["prompt_template"]


def test_resolve_short_answer_ai_scoring_allows_spec_override() -> None:
    spec = {
        "series_index": 2,
        "ai_scoring": {
            "pass_threshold": 80,
            "system_prompt": "自定义系统提示",
        },
    }
    config = resolve_short_answer_ai_scoring(spec)
    assert config["pass_threshold"] == 80
    assert config["system_prompt"] == "自定义系统提示"
    assert "系列之2" in config["prompt_template"]
