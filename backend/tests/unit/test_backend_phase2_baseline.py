def test_should_import_phase2_baseline_modules_without_side_effects() -> None:
    import curriculum_practice.models
    import curriculum_practice.schemas
    import curriculum_practice.services.publishing_gates
    import curriculum_practice.services.snapshots
    import evaluation.services.evaluation_run_service

    assert curriculum_practice.models.PracticeTemplate.__tablename__ == "practice_templates"
