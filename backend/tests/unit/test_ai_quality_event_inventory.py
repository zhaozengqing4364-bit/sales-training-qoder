from common.ai import llm_service as llm_module
import sales_bot.websocket.stepfun_realtime_handler as stepfun_module


def _event_ids(entries: tuple[dict[str, object], ...]) -> set[str]:
    return {
        str(entry.get("event_id") or "")
        for entry in entries
        if isinstance(entry, dict)
    }


def test_llm_service_inventory_names_hidden_default_and_cost_surfaces():
    event_ids = _event_ids(llm_module.LLM_RUNTIME_EVENT_INVENTORY)

    assert {
        "llm_fallback_response",
        "llm_evaluation_default_scores",
        "llm_report_generation_failed",
        "llm_cost_tracking_coarse_session_total",
    } <= event_ids


def test_stepfun_inventory_names_runtime_degradation_and_knowledge_mode_surfaces():
    event_ids = _event_ids(stepfun_module.STEPFUN_RUNTIME_EVENT_INVENTORY)

    assert {
        "kb_lock_warmup_degraded",
        "capability_pipeline_failed",
        "knowledge_answer_rollout_mode",
        "browser_tts_fallback",
        "transcription_timeout_blocked",
    } <= event_ids
