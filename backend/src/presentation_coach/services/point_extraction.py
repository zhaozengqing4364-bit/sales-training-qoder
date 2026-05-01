"""
AI-Assisted Talking Point Extraction - Extracts required talking points from PPT content

Implements Constitution Principles:
- I. NO ERROR POPUPS - Graceful degradation
- V. Cost control - Efficient prompt engineering
"""

import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from common.ai.llm_service import get_llm_service
from common.error_handling.result import Result
from common.ppt.ocr_processor import PPTPage

logger = logging.getLogger(__name__)


class ExtractedPoints(BaseModel):
    """Extracted talking points from LLM"""

    required_points: list[str] = Field(
        description="List of required talking points for this slide"
    )
    key_concepts: list[str] = Field(description="Key concepts that should be mentioned")
    success_criteria: list[str] = Field(description="What makes this slide successful")


class PointExtractionService:
    """
    Extracts required talking points from PPT content using LLM

    Key features:
    - Analyzes PPT content
    - Identifies key talking points
    - Suggests what should be covered
    - Helps admins configure coaching
    """

    def __init__(self):
        self.parser = PydanticOutputParser(pydantic_object=ExtractedPoints)

        self.extraction_prompt = PromptTemplate(
            template="""Analyze this PPT slide and identify the required talking points.

**Slide Title**: {title}

**Slide Content**:
{content}

**Context**: This is a {page_context} slide.

Your task:
1. Identify 3-5 key talking points that MUST be covered when presenting this slide
2. Identify key concepts that should be mentioned
3. Define success criteria for this slide

{format_instructions}

Provide actionable, specific talking points.""",
            input_variables=["title", "content", "page_context"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            },
        )

    async def extract_points_for_page(
        self, page: PPTPage, page_context: str = "general"
    ) -> Result[ExtractedPoints]:
        """
        Extract talking points for a single page

        Returns: ExtractedPoints or Result.fail
        """
        try:
            # Generate prompt
            prompt_value = self.extraction_prompt.format(
                title=page.title,
                content=page.content or "No text content",
                page_context=page_context,
            )

            # Call LLM
            response = await get_llm_service().llm.apredict(prompt_value)

            # Parse response
            points = self.parser.parse(response)

            logger.info(
                "Talking points extracted",
                extra={
                    "page_number": page.page_number,
                    "points_count": len(points.required_points),
                },
            )

            return Result(value=points)

        except TimeoutError:
            logger.warning(
                "LLM timeout extracting points", extra={"page_number": page.page_number}
            )
            # Fallback to rule-based extraction
            return Result(value=self._extract_points_fallback(page))
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to extract points",
                extra={"page_number": page.page_number, "error": str(e)},
                exc_info=True,
            )
            return Result.fail(fallback="[EXTRACTION_FAILED]")

    async def extract_points_for_presentation(
        self, pages: list[PPTPage]
    ) -> Result[dict[int, ExtractedPoints]]:
        """
        Extract talking points for all pages in a presentation

        Returns: Dict mapping page_number -> ExtractedPoints or Result.fail
        """
        try:
            results = {}

            for page in pages:
                result = await self.extract_points_for_page(page)

                if result.is_success:
                    results[page.page_number] = result.value
                else:
                    # Use fallback for this page
                    results[page.page_number] = self._extract_points_fallback(page)

            logger.info(
                "Talking points extracted for presentation",
                extra={"total_pages": len(pages), "extracted": len(results)},
            )

            return Result(value=results)

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(
                "Failed to extract points for presentation",
                extra={"error": str(e)},
                exc_info=True,
            )
            return Result.fail(fallback="[EXTRACTION_FAILED]")

    def _extract_points_fallback(self, page: PPTPage) -> ExtractedPoints:
        """
        Fallback: Rule-based talking point extraction

        Uses simple heuristics when LLM fails
        """
        # Generate generic talking points
        required_points = [
            f"Explain the main topic: {page.title}",
        ]

        # Extract key concepts from content (sentences)
        if page.content:
            sentences = [s.strip() for s in page.content.split(".") if s.strip()]
            key_concepts = sentences[:3]  # First 3 sentences as key concepts
        else:
            key_concepts = [f"Main concept of {page.title}"]

        # Success criteria
        success_criteria = [
            "Cover all key points clearly",
            "Maintain audience engagement",
            "Use appropriate pace and tone",
        ]

        return ExtractedPoints(
            required_points=required_points,
            key_concepts=key_concepts,
            success_criteria=success_criteria,
        )


# Singleton instance
point_extraction_service = PointExtractionService()
