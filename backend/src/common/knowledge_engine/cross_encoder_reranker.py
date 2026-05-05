"""
Cross-Encoder Reranker — neural reranking for knowledge search results.

Supports two backends:
  - ``local``: sentence-transformers cross-encoder model loaded in-process
    (e.g. BAAI/bge-reranker-v2-m3).  Runs inference via ``asyncio.to_thread``
    to avoid blocking the event loop.
  - ``cohere``: Cohere Rerank API (requires ``COHERE_API_KEY`` env var).

The module is intentionally lightweight: it exposes a single async ``rerank()``
method that returns normalised [0, 1] scores, compatible with the existing
``_fuse_retrieval_results()`` pipeline in ``service.py``.

References:
    - Plan Phase 5: Cross-Encoder Reranker
    - Replaces/wraps: service.py _rerank_results() rule-based reranker
"""

from __future__ import annotations

import asyncio
import importlib
import os
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CrossEncoderReranker:
    """Neural cross-encoder reranker with pluggable backends.

    Parameters
    ----------
    backend:
        ``"local"`` or ``"cohere"``.
    model_name:
        Model identifier for the chosen backend.
    device:
        Torch device hint for local models (default ``"cpu"``).
    api_key:
        API key for remote backends.  Falls back to ``COHERE_API_KEY`` env var.
    max_length:
        Max token length for local model tokenisation.
    """

    def __init__(
        self,
        *,
        backend: str = "local",
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        api_key: str | None = None,
        max_length: int = 512,
    ) -> None:
        self.backend = backend
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self._api_key = api_key
        self._model: Any = None
        self._model_loaded = False
        self._model_failed = False

    # ── Public API ──

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        """Rerank *documents* against *query*, returning at most *top_k*.

        Each element of *documents* must contain a ``"content"`` key.  The
        returned list is sorted descending by the cross-encoder score (normalised
        to [0, 1]).  On any failure the original ordering is returned unchanged.
        """
        if not documents or not query.strip():
            return documents[: max(1, top_k)]

        started_at = time.monotonic()
        try:
            if self.backend == "local":
                results = await self._rerank_local(query, documents, top_k)
            elif self.backend == "cohere":
                results = await self._rerank_cohere(query, documents, top_k)
            else:
                logger.warning(
                    "Unknown cross-encoder backend, passthrough", backend=self.backend
                )
                return documents[: max(1, top_k)]

            elapsed_ms = round((time.monotonic() - started_at) * 1000, 1)
            logger.debug(
                "Cross-encoder rerank completed",
                backend=self.backend,
                model=self.model_name,
                input_count=len(documents),
                output_count=len(results),
                elapsed_ms=elapsed_ms,
            )
            return results

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Cross-encoder rerank failed, returning original order",
                backend=self.backend,
                error=str(exc),
            )
            return documents[: max(1, top_k)]

    # ── Local backend ──

    def _ensure_model(self) -> bool:
        """Lazily load the cross-encoder model (synchronous)."""
        if self._model_loaded:
            return True
        if self._model_failed:
            return False
        try:
            sentence_transformers = importlib.import_module("sentence_transformers")
            CrossEncoder = getattr(sentence_transformers, "CrossEncoder")

            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=self.max_length,
            )
            self._model_loaded = True
            logger.info(
                "Cross-encoder model loaded", model=self.model_name, device=self.device
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self._model_failed = True
            logger.warning(
                "Failed to load cross-encoder model",
                model=self.model_name,
                error=str(exc),
            )
            return False

    async def _rerank_local(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if not self._ensure_model():
            return documents[: max(1, top_k)]

        pairs = [(query, str(doc.get("content", ""))) for doc in documents]
        scores = await asyncio.to_thread(self._model.predict, pairs)

        # Normalise scores to [0, 1]
        raw_scores = [float(s) for s in scores]
        min_s = min(raw_scores) if raw_scores else 0.0
        max_s = max(raw_scores) if raw_scores else 1.0
        range_s = max_s - min_s if max_s > min_s else 1.0

        scored: list[tuple[float, dict[str, Any]]] = []
        for i, raw in enumerate(raw_scores):
            normalised = round((raw - min_s) / range_s, 4) if range_s > 0 else 0.5
            row = dict(documents[i])
            row["cross_encoder_score"] = normalised
            row["rerank_strategy"] = "cross_encoder_local"
            scored.append((normalised, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[: max(1, top_k)]]

    # ── Cohere backend ──

    async def _rerank_cohere(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        api_key = self._api_key or os.getenv("COHERE_API_KEY")
        if not api_key:
            logger.warning("COHERE_API_KEY not set, skipping Cohere rerank")
            return documents[: max(1, top_k)]

        import httpx

        texts = [str(doc.get("content", "")) for doc in documents]
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.cohere.ai/v1/rerank",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "query": query,
                    "documents": texts,
                    "top_n": min(top_k, len(texts)),
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results_data = data.get("results", [])
        if not results_data:
            return documents[: max(1, top_k)]

        output: list[dict[str, Any]] = []
        for item in results_data:
            idx = int(item.get("index", 0))
            if idx >= len(documents):
                continue
            row = dict(documents[idx])
            row["cross_encoder_score"] = round(
                float(item.get("relevance_score", 0.0)), 4
            )
            row["rerank_strategy"] = "cross_encoder_cohere"
            output.append(row)

        output.sort(key=lambda r: float(r.get("cross_encoder_score", 0)), reverse=True)
        return output[: max(1, top_k)]


# ── Singleton ──

_cross_encoder: CrossEncoderReranker | None = None


def get_cross_encoder_reranker() -> CrossEncoderReranker | None:
    """Get the global cross-encoder reranker (if configured).

    Enabled via env var ``CROSS_ENCODER_BACKEND`` (``local`` | ``cohere``).
    Returns ``None`` if not configured, signalling callers to use the default
    rule-based reranker.
    """
    global _cross_encoder

    backend = os.getenv("CROSS_ENCODER_BACKEND", "").strip().lower()
    if not backend:
        return None

    if _cross_encoder is None:
        model_name = os.getenv(
            "CROSS_ENCODER_MODEL",
            "BAAI/bge-reranker-v2-m3" if backend == "local" else "rerank-v3.5",
        )
        device = os.getenv("CROSS_ENCODER_DEVICE", "cpu")
        api_key = os.getenv("COHERE_API_KEY") or None

        _cross_encoder = CrossEncoderReranker(
            backend=backend,
            model_name=model_name,
            device=device,
            api_key=api_key,
        )

        logger.info(
            "Cross-encoder reranker configured",
            backend=backend,
            model=model_name,
        )

    return _cross_encoder
