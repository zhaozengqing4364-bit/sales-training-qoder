from common.db.model_registry.registration import (
    PERSISTENCE_MODEL_MODULES,
    register_all_models,
)


def test_root_model_registration_includes_every_domain_owned_table() -> None:
    metadata = register_all_models()

    expected_tables = {
        "agents",
        "voice_runtime_profiles",
        "model_configs",
        "knowledge_bases",
        "knowledge_dictionary_entries",
        "rag_profiles",
        "practice_templates",
        "durable_tasks",
        "outbox_events",
        "ai_invocations",
        "ai_usage_ledger",
        "learner_profiles",
        "sales_trainer_units",
        "sales_trainer_regrade_runs",
        "teams",
        "provisioning_batches",
        "coach_profile_revisions",
        "coach_sessions",
        "coach_remediation_cycles",
        "coach_turns",
        "coach_training_cards",
        "coach_card_responses",
        "coach_assistances",
        "coach_outcomes",
        "coach_human_interventions",
        "coach_command_audits",
    }

    assert expected_tables <= set(metadata.tables)


def test_regrade_models_are_part_of_the_authoritative_registration_list() -> None:
    assert "sales_trainer.regrade_models" in PERSISTENCE_MODEL_MODULES


def test_task_and_ai_platform_models_are_authoritatively_registered() -> None:
    assert "task_runtime.models" in PERSISTENCE_MODEL_MODULES
    assert "ai_platform.models" in PERSISTENCE_MODEL_MODULES
    assert "ai_coach.models" in PERSISTENCE_MODEL_MODULES
