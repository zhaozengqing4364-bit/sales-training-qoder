"""
ChromaDB Ingestion Service - Ingests PPT pages into vector store

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful degradation on ingestion failure
- V. Cost control - Efficient embedding usage
"""

import logging
import uuid

from common.error_handling.result import Result
from common.knowledge.vector_store import get_vector_store
from common.monitoring.logger import get_logger
from common.ppt.ocr_processor import PPTExtraction

logger = get_logger(__name__)


class IngestionService:
    """
    Ingests PPT content into ChromaDB vector store

    Key responsibilities:
    - Convert PPT pages to embeddings
    - Store in ChromaDB with metadata
    - Enable semantic search during coaching
    """

    def __init__(self):
        self.collection_name = "presentations"
        self._vector_store = None  # Lazy reference

    def _get_vector_store(self):
        """Lazy get vector store"""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    async def ingest_presentation(
        self,
        extraction: PPTExtraction
    ) -> Result[bool]:
        """
        Ingest all pages from a PPT into vector store

        Returns: True or Result.fail
        """
        try:
            # Collect all page texts
            texts = []
            metadatas = []
            ids = []

            for page in extraction.pages:
                # Combine title and content
                full_text = f"{page.title}\n{page.content}"

                texts.append(full_text)

                # Metadata for filtering
                metadatas.append({
                    "presentation_id": str(extraction.presentation_id),
                    "page_number": page.page_number,
                    "title": page.title,
                    "filename": extraction.filename,
                })

                # Unique ID
                ids.append(f"{extraction.presentation_id}_page_{page.page_number}")

            # Add to vector store
            result = await self._get_vector_store().add_documents(
                collection_name=self.collection_name,
                texts=texts,
                metadatas=metadatas,
                ids=ids
            )

            if not result.is_success:
                logger.error(
                    "Failed to add documents to vector store",
                    extra={"presentation_id": str(extraction.presentation_id)}
                )
                return Result.fail(fallback="[INGESTION_FAILED]")

            logger.info(
                "Presentation ingested into vector store",
                extra={
                    "presentation_id": str(extraction.presentation_id),
                    "pages": len(texts),
                }
            )

            return Result(value=True)

        except Exception as e:
            logger.error(
                "Failed to ingest presentation",
                extra={"presentation_id": str(extraction.presentation_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[INGESTION_FAILED]")

    async def update_page(
        self,
        presentation_id: uuid.UUID,
        page_number: int,
        title: str,
        content: str,
        filename: str
    ) -> Result[bool]:
        """
        Update a single page in the vector store

        Returns: True or Result.fail
        """
        try:
            # Combine title and content
            full_text = f"{title}\n{content}"

            # Metadata
            metadata = {
                "presentation_id": str(presentation_id),
                "page_number": page_number,
                "title": title,
                "filename": filename,
            }

            # Unique ID
            doc_id = f"{presentation_id}_page_{page_number}"

            # Update in vector store
            result = await self._get_vector_store().update_document(
                collection_name=self.collection_name,
                doc_id=doc_id,
                text=full_text,
                metadata=metadata
            )

            if not result.is_success:
                # If update fails, try adding instead
                add_result = await self._get_vector_store().add_documents(
                    collection_name=self.collection_name,
                    texts=[full_text],
                    metadatas=[metadata],
                    ids=[doc_id]
                )

                if not add_result.is_success:
                    return Result.fail(fallback="[UPDATE_FAILED]")

            logger.info(
                "Page updated in vector store",
                extra={
                    "presentation_id": str(presentation_id),
                    "page_number": page_number,
                }
            )

            return Result(value=True)

        except Exception as e:
            logger.error(
                "Failed to update page",
                extra={
                    "presentation_id": str(presentation_id),
                    "page_number": page_number,
                    "error": str(e)
                },
                exc_info=True
            )
            return Result.fail(fallback="[UPDATE_FAILED]")

    async def delete_presentation(
        self,
        presentation_id: uuid.UUID
    ) -> Result[bool]:
        """
        Delete all pages for a presentation from vector store

        Returns: True or Result.fail
        """
        try:
            # Delete by metadata filter
            result = await self._get_vector_store().delete_by_metadata(
                collection_name=self.collection_name,
                metadata_filter={"presentation_id": str(presentation_id)}
            )

            if not result.is_success:
                return Result.fail(fallback="[DELETE_FAILED]")

            logger.info(
                "Presentation deleted from vector store",
                extra={"presentation_id": str(presentation_id)}
            )

            return Result(value=True)

        except Exception as e:
            logger.error(
                "Failed to delete presentation",
                extra={"presentation_id": str(presentation_id), "error": str(e)},
                exc_info=True
            )
            return Result.fail(fallback="[DELETE_FAILED]")

    async def search_similar_pages(
        self,
        query: str,
        presentation_id: uuid.UUID,
        page_number: int,
        n_results: int = 3
    ) -> Result[list[dict]]:
        """
        Search for similar pages in the presentation

        Used by coach to find related content

        Returns: List of similar pages or Result.fail
        """
        try:
            result = await self._get_vector_store().query(
                collection_name=self.collection_name,
                query_texts=[query],
                where={
                    "presentation_id": str(presentation_id),
                    "page_number": {"$ne": page_number}  # Exclude current page
                },
                n_results=n_results
            )

            if not result.is_success:
                return Result.fail(fallback="[SEARCH_FAILED]")

            logger.info(
                "Similar pages search complete",
                extra={
                    "presentation_id": str(presentation_id),
                    "page_number": page_number,
                    "results": len(result.value),
                }
            )

            return Result(value=result.value)

        except Exception as e:
            logger.error(
                "Failed to search similar pages",
                extra={
                    "presentation_id": str(presentation_id),
                    "page_number": page_number,
                    "error": str(e)
                },
                exc_info=True
            )
            return Result.fail(fallback="[SEARCH_FAILED]")


# Singleton instance
ingestion_service = IngestionService()
