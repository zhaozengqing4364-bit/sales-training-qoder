"""
LLM Response Validation Schemas with Pydantic

Requirements: Task #4 - Add LLM response validation with Pydantic

This module provides Pydantic models for validating LLM responses in the
evaluation system. It includes schemas for both stage evaluations and
comprehensive reports, with proper error handling using Result[T] pattern.

Features:
- StageEvaluationResponse: Validates stage-level evaluation responses
- ComprehensiveReportResponse: Validates comprehensive report responses
- parse_response_llm(): Generic parser with Result[T] error handling
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class StageEvaluationResponse(BaseModel):
    """Validated LLM response for stage evaluation.

    Attributes:
        scores: Dictionary of dimension scores (e.g., {"communication": 85.0})
        strengths: List of identified strengths
        suggestions: List of improvement suggestions
        summary: Brief summary of the stage performance
        confidence: AI confidence level (0.0-1.0)
    """

    scores: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    summary: str = Field(default="")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ComprehensiveReportDimensionScore(BaseModel):
    """Dimension score in comprehensive report response."""

    name: str = Field(..., description="Dimension name")
    score: float = Field(..., ge=0.0, le=100.0, description="Score 0-100")
    weight: float = Field(default=0.2, description="Dimension weight")
    description: str = Field(default="", description="Dimension description")


class ComprehensiveReportStageSummary(BaseModel):
    """Stage summary in comprehensive report response."""

    stage_number: int = Field(..., description="Stage number")
    start_turn: int = Field(default=0, description="Start turn index")
    end_turn: int = Field(default=0, description="End turn index")
    average_score: float = Field(default=0.0, description="Average score for this stage")
    key_points: list[str] = Field(default_factory=list, description="Key points")
    summary: str = Field(default="", description="Stage summary text")


class ComprehensiveReportResponse(BaseModel):
    """API response for comprehensive report.

    Attributes:
        session_id: Practice session ID
        generated_at: Report generation timestamp
        overall_score: Overall performance score (0-100)
        dimension_scores: Dimension-specific scores (legacy dict or structured list)
        key_strengths: List of key strengths identified
        key_improvements: List of key areas for improvement
        recommendations: List of actionable recommendations
        detailed_feedback: Detailed narrative feedback
        stage_summaries: Stage summaries (legacy dict or structured list)
    """

    session_id: str = Field(default="", description="Practice session ID")
    generated_at: str = Field(default="", description="Report generation timestamp (ISO format)")
    overall_score: float = Field(..., ge=0.0, le=100.0)
    dimension_scores: dict[str, float] | list[ComprehensiveReportDimensionScore] = Field(default_factory=dict)
    key_strengths: list[str] = Field(default_factory=list)
    key_improvements: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    detailed_feedback: str = Field(default="")
    stage_summaries: dict[str, Any] | list[ComprehensiveReportStageSummary] = Field(default_factory=dict)


class DimensionScore(BaseModel):
    """Score for a single dimension with detailed breakdown.

    Attributes:
        name: Dimension name
        score: Score value (0-100)
        reason: Explanation for this score
        positive_indicators: List of positive behaviors detected
        negative_indicators: List of negative behaviors detected
    """

    name: str = Field(..., description="Dimension name")
    score: float = Field(..., ge=0.0, le=100.0, description="Score 0-100")
    reason: str = Field(default="", max_length=200, description="Reason for this score")
    positive_indicators: list[str] = Field(
        default_factory=list, description="Positive behaviors detected"
    )
    negative_indicators: list[str] = Field(
        default_factory=list, description="Negative behaviors detected"
    )


class RealtimeScoringResponse(BaseModel):
    """Validated LLM response for realtime scoring evaluation.

    Attributes:
        overall_score: Overall performance score (0-100)
        dimensions: Dictionary of dimension-specific scores with reasons
        feedback: Brief feedback message for user
        confidence: AI confidence level in its assessment (0.0-1.0)
        reasoning: Optional explanation of scoring logic
    """

    overall_score: float = Field(..., ge=0.0, le=100.0)
    dimensions: dict[str, DimensionScore] = Field(default_factory=dict)
    feedback: str = Field(default="", max_length=200)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: str = Field(default="", max_length=500)


class RealtimeEvaluationFeedback(BaseModel):
    stage_number: int
    timestamp: str
    scores: dict[str, float] = Field(default_factory=dict)
    feedback: str = Field(default="", description="Stage summary")
    suggestions: list[str] = Field(
        default_factory=list, description="Improvement suggestions"
    )
    trigger_type: str = Field(
        default="turn_count",
        description="Trigger type: turn_count, time_interval, keyword, or stage_transition",
    )


async def parse_llm_response(
    response_data: str | dict | bytes,
    schema_class: type[BaseModel],
) -> Result[BaseModel]:
    """Parse and validate LLM response with Pydantic schema.

    This function handles various input formats (JSON string, dict, bytes)
    and validates them against the provided Pydantic schema. Returns
    Result[T] for error-free operation per Constitution Principle I.

    Args:
        response_data: LLM response data (JSON string, dict, or bytes)
        schema_class: Pydantic model class for validation

    Returns:
        Result containing validated model or error details on failure

    Examples:
        >>> result = await parse_llm_response(
        ...     '{"scores": {"comm": 85}, "strengths": ["clear"]}',
        ...     StageEvaluationResponse
        ... )
        >>> if result.is_success:
        ...     evaluation = result.value
        >>>     logger.info("scores=%s", evaluation.scores)
    """
    try:
        # Parse JSON string if input is str
        if isinstance(response_data, str):
            try:
                parsed_data = json.loads(response_data)
            except json.JSONDecodeError as e:
                logger.error(
                    "llm_parse_json_decode_error",
                    error=str(e),
                    response_preview=response_data[:200],
                )
                return Result.fail(
                    f"[LLM_PARSE_JSON_ERROR: Invalid JSON format - {str(e)}]"
                )

        # Parse bytes if input is bytes
        elif isinstance(response_data, bytes):
            try:
                decoded_str = response_data.decode("utf-8")
                parsed_data = json.loads(decoded_str)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(
                    "llm_parse_bytes_decode_error",
                    error=str(e),
                )
                return Result.fail(
                    f"[LLM_PARSE_BYTES_ERROR: Cannot decode bytes - {str(e)}]"
                )

        # Use dict directly if input is already dict
        elif isinstance(response_data, dict):
            parsed_data = response_data

        else:
            logger.error(
                "llm_parse_unsupported_type",
                input_type=type(response_data).__name__,
            )
            return Result.fail(
                f"[LLM_PARSE_TYPE_ERROR: Unsupported type {type(response_data).__name__}]"
            )

        # Validate against Pydantic schema
        validated_model = schema_class(**parsed_data)

        logger.info(
            "llm_parse_success",
            schema=schema_class.__name__,
            fields_count=len(schema_class.model_fields),
        )

        return Result.ok(validated_model)

    except ValidationError as e:
        # Log validation errors with structlog
        error_details = e.errors()
        logger.error(
            "llm_parse_validation_error",
            schema=schema_class.__name__,
            error_count=len(error_details),
            errors=error_details,
            response_preview=str(response_data)[:500],
        )

        # Build user-friendly error message
        error_messages = []
        for error in error_details:
            field = " -> ".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            error_messages.append(f"{field}: {msg}")

        error_detail = "; ".join(error_messages)
        return Result.fail(
            f"[LLM_VALIDATION_ERROR: {schema_class.__name__} - {error_detail}]"
        )

    except (RuntimeError, ValueError, TypeError) as e:
        # Catch any unexpected errors
        logger.error(
            "llm_parse_unexpected_error",
            schema=schema_class.__name__,
            error=str(e),
            error_type=type(e).__name__,
        )
        return Result.fail(f"[LLM_PARSE_ERROR: {schema_class.__name__} - {str(e)}]")
