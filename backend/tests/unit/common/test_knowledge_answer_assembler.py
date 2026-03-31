from common.knowledge_engine.answerability import KnowledgeAnswerabilityResult
from common.knowledge_engine.assembler import KnowledgeAnswerAssembler
from common.knowledge_engine.haystack_adapter import (
    KnowledgeExecutedQueryStep,
    KnowledgeHaystackExecutionResult,
)


def _execution_result(*, failures: list[str] | None = None) -> KnowledgeHaystackExecutionResult:
    return KnowledgeHaystackExecutionResult(
        executed_steps=[
            KnowledgeExecutedQueryStep(
                query="介绍一下企业版",
                stage="primary",
                profile_key="product_overview",
                status="hit",
                hit_count=2,
                retrieval_modes=["hybrid"],
            )
        ],
        search_failures=list(failures or []),
    )


def test_assemble_returns_grounded_answer_text_and_citations_from_supported_rows():
    assembler = KnowledgeAnswerAssembler()

    result = assembler.assemble(
        query="介绍一下企业版",
        rows=[
            {
                "document_id": "doc-1",
                "document_title": "企业版产品手册",
                "chunk_id": "chunk-1",
                "snippet": "企业版支持销售训练流程编排与复盘。",
                "content": "企业版支持销售训练流程编排与复盘。",
                "score": 0.93,
            },
            {
                "document_id": "doc-2",
                "document_title": "部署指南",
                "chunk_id": "chunk-2",
                "snippet": "企业版可接入企业内部知识库并保留审计轨迹。",
                "content": "企业版可接入企业内部知识库并保留审计轨迹。",
                "score": 0.88,
            },
        ],
        answerability_result=KnowledgeAnswerabilityResult(
            answerability="sufficient",
            source_status="ready",
            audit={"mode": "slot_coverage"},
        ),
        execution_result=_execution_result(),
    )

    assert result.answerability == "sufficient"
    assert result.source_status == "ready"
    assert result.blocked_text is None
    assert result.final_text == "根据知识库证据：\n1. 企业版支持销售训练流程编排与复盘。\n2. 企业版可接入企业内部知识库并保留审计轨迹。"
    assert result.unsupported_claims == []
    assert [citation.document_title for citation in result.citations] == ["企业版产品手册", "部署指南"]
    assert result.citations[0].snippet == "企业版支持销售训练流程编排与复盘。"
    assert result.rewritten_queries == ["介绍一下企业版"]
    assert result.retrieval_summary == {
        "hit_count": 2,
        "executed_query_count": 1,
        "search_failure_count": 0,
        "blocked_reason": None,
    }


def test_assemble_returns_blocked_text_and_empty_answer_when_answerability_is_blocked():
    assembler = KnowledgeAnswerAssembler()

    result = assembler.assemble(
        query="介绍一下企业版",
        rows=[],
        answerability_result=KnowledgeAnswerabilityResult(
            answerability="blocked",
            source_status="blocked",
            audit={"blocked_reason": "retrieval_failed"},
        ),
        execution_result=_execution_result(failures=["embedding timeout"]),
    )

    assert result.final_text is None
    assert result.blocked_text == "当前无法基于知识库证据生成回答，请稍后重试。"
    assert result.citations == []
    assert result.unsupported_claims == []
    assert result.retrieval_summary == {
        "hit_count": 0,
        "executed_query_count": 1,
        "search_failure_count": 1,
        "blocked_reason": "retrieval_failed",
    }


def test_assemble_tracks_rows_without_grounded_snippets_as_unsupported_claims():
    assembler = KnowledgeAnswerAssembler()

    result = assembler.assemble(
        query="介绍一下企业版",
        rows=[
            {
                "document_id": "doc-1",
                "document_title": "企业版产品手册",
                "chunk_id": "chunk-1",
                "snippet": "企业版支持销售训练流程编排与复盘。",
                "content": "企业版支持销售训练流程编排与复盘。",
                "score": 0.93,
            },
            {
                "document_id": "doc-2",
                "document_title": "话术草稿",
                "chunk_id": "chunk-2",
                "content": "企业版覆盖全部行业解决方案",
                "score": 0.35,
            },
        ],
        answerability_result=KnowledgeAnswerabilityResult(
            answerability="partial",
            source_status="ready",
            audit={"mode": "slot_coverage"},
        ),
        execution_result=_execution_result(),
    )

    assert result.answerability == "partial"
    assert result.final_text == "根据知识库证据：\n1. 企业版支持销售训练流程编排与复盘。"
    assert result.unsupported_claims == ["企业版覆盖全部行业解决方案"]
    assert [citation.document_title for citation in result.citations] == ["企业版产品手册"]
