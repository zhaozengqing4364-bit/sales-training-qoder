from __future__ import annotations

from collections.abc import Callable
from typing import Any

from common.knowledge_engine.schemas import KnowledgeAnswerRequest, KnowledgeAnswerResult


HaystackPipelineFactory = Callable[[], Any | None]


class KnowledgeAnswerEngine:
    """Minimal knowledge-answer seam.

    This task only establishes the project-owned entrypoint and result contract.
    Retrieval/reranking/answerability logic will be wired in later slices.
    """

    def __init__(
        self,
        *,
        haystack_pipeline_factory: HaystackPipelineFactory | None = None,
    ) -> None:
        self._haystack_pipeline_factory = (
            haystack_pipeline_factory or default_haystack_pipeline_factory
        )

    @property
    def haystack_pipeline_factory(self) -> HaystackPipelineFactory:
        return self._haystack_pipeline_factory

    def answer(self, request: KnowledgeAnswerRequest) -> KnowledgeAnswerResult:
        """Return the project-owned placeholder contract until execution logic lands."""
        _ = request
        return KnowledgeAnswerResult()


def default_haystack_pipeline_factory() -> Any | None:
    """Soft dependency seam for Haystack.

    The package is declared in project metadata, but the engine stays constructable even
    before the runtime environment has installed it.
    """

    try:
        from haystack import Pipeline
    except ImportError:
        return None

    return Pipeline()
