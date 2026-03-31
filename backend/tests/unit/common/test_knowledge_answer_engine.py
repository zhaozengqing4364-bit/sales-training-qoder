from common.knowledge_engine.engine import KnowledgeAnswerEngine
from common.knowledge_engine.schemas import KnowledgeAnswerRequest


def test_engine_can_be_constructed_with_default_dependencies():
    engine = KnowledgeAnswerEngine()

    assert engine is not None


def test_engine_answer_returns_placeholder_contract_with_observability_fields():
    engine = KnowledgeAnswerEngine()

    result = engine.answer(
        KnowledgeAnswerRequest(
            query="介绍一下企业版",
            knowledge_base_ids=["kb-1"],
        )
    )

    assert result.final_text is None
    assert result.blocked_text is None
    assert result.answerability == "unanswered"
    assert result.source_status == "not_run"
    assert result.citations == []
    assert result.rewritten_queries == []
    assert result.unsupported_claims == []
    assert result.audit_run_id is None
    assert result.retrieval_summary == {}
