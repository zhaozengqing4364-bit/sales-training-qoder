from __future__ import annotations

from evaluation.api import _report_generation_error_response


def test_report_generation_no_stage_results_returns_business_error() -> None:
    response = _report_generation_error_response(
        detail="[NO_STAGE_RESULTS]",
        session_id="session-1",
    )

    assert response.status_code == 422
    assert response.body
    assert b"[NO_STAGE_RESULTS]" in response.body
    assert "缺少阶段评估结果" in response.body.decode("utf-8")


def test_report_generation_database_error_preserves_error_type() -> None:
    response = _report_generation_error_response(
        detail="[DATABASE_ERROR:commit failed]",
        session_id="session-1",
    )

    assert response.status_code == 500
    assert response.body
    assert b"[DATABASE_ERROR]" in response.body
    body = response.body.decode("utf-8")
    assert "commit failed" not in body
    assert "报告生成失败" in body


def test_report_generation_storage_error_preserves_error_type() -> None:
    response = _report_generation_error_response(
        detail="[STORAGE_ERROR:unexpected failure]",
        session_id="session-1",
    )

    assert response.status_code == 500
    assert response.body
    assert b"[STORAGE_ERROR]" in response.body
    body = response.body.decode("utf-8")
    assert "unexpected failure" not in body
    assert "报告生成失败" in body


def test_report_generation_unknown_error_falls_back_to_generic_failure() -> None:
    response = _report_generation_error_response(
        detail="[SOMETHING_ELSE:internal traceback]",
        session_id="session-1",
    )

    assert response.status_code == 500
    assert response.body
    body = response.body.decode("utf-8")
    assert b"[REPORT_GENERATION_FAILED]" in response.body
    assert "[NO_STAGE_RESULTS]" not in body
    assert "[DATABASE_ERROR]" not in body
    assert "[STORAGE_ERROR]" not in body
    assert "internal traceback" not in body
