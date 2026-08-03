from __future__ import annotations

from pathlib import Path

RUNBOOK = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "setup"
    / "foundation-operations-runbook.md"
)


def test_foundation_operations_runbook_covers_release_incidents_and_safe_controls() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")

    for incident_id in range(1, 11):
        assert f"OPS-{incident_id:02d}" in content
    for alert_id in (
        "FND-API-01",
        "FND-TASK-01",
        "FND-TASK-02",
        "FND-UPLOAD-01",
        "FND-AI-01",
        "FND-AI-02",
        "FND-DOSSIER-01",
        "FND-RELEASE-01",
        "FND-SEC-01",
    ):
        assert alert_id in content
    for contract in (
        "http_requests_total",
        "http_request_duration_seconds",
        "/api/v1/admin/task-runtime/health",
        "/api/v1/admin/task-runtime/tasks/{task_id}/redrive",
        "/api/v1/admin/task-runtime/task-types/{task_type}/pause",
        "/api/v1/admin/newcomer-training/reviews/{dossier_id}/rebuild",
        "scripts/cleanup_foundation_audio_uploads.py --limit 100",
        "foundation-release-runbook.md",
        "durable-task-worker-runbook.md",
    ):
        assert contract in content
    for safety_rule in (
        "不得 `UPDATE durable_tasks`",
        "不得记录录音、答案、转写全文",
        "不能作为发布通过",
        "foundation_ready",
    ):
        assert safety_rule in content
