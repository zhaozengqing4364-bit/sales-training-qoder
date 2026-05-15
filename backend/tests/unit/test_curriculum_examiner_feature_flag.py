from common.api.feature_flags import read_feature_flags
from common.config import Settings


def test_should_default_curriculum_examiner_feature_flag_to_disabled(monkeypatch):
    monkeypatch.delenv("CURRICULUM_EXAMINER_ENABLED", raising=False)

    flags = read_feature_flags(Settings())

    assert flags == {"curriculum": {"examiner": False}}


def test_should_read_enabled_curriculum_examiner_feature_flag(monkeypatch):
    monkeypatch.setenv("CURRICULUM_EXAMINER_ENABLED", "true")

    flags = read_feature_flags(Settings())

    assert flags["curriculum"]["examiner"] is True
