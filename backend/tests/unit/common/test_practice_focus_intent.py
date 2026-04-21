from common.services.practice_helpers import PracticeRetryEntryAssembler


def test_sanitize_focus_intent_accepts_presentation_page_focus():
    sanitized = PracticeRetryEntryAssembler.sanitize_focus_intent(
        {
            "version": "presentation_page_retry_v1",
            "source_session_id": "session-source",
            "presentation_page": {
                "page_number": "2",
                "reason": " missing_required_points ",
                "summary": "第 2 页缺客户案例",
                "missing_required_points": ["客户案例", "", None],
            },
            "ignored": "drop-me",
        }
    )

    assert sanitized == {
        "version": "presentation_page_retry_v1",
        "source_session_id": "session-source",
        "presentation_page": {
            "page_number": 2,
            "reason": "missing_required_points",
            "summary": "第 2 页缺客户案例",
            "missing_required_points": ["客户案例"],
        },
    }


def test_sanitize_focus_intent_rejects_invalid_presentation_page_without_other_focus():
    assert PracticeRetryEntryAssembler.sanitize_focus_intent(
        {
            "version": "presentation_page_retry_v1",
            "source_session_id": "session-source",
            "presentation_page": {"page_number": 0},
        }
    ) is None


def test_practice_session_service_reexports_retry_assembler_for_compatibility():
    from common.services.practice_session_service import (
        PracticeRetryEntryAssembler as ReexportedAssembler,
    )

    assert ReexportedAssembler is PracticeRetryEntryAssembler
