"""
Unit Tests for Evaluation Schemas

Requirements: Task #8 - Add unit tests for evaluation module
Coverage Target: 80% for schemas.py

Test Coverage:
- StageEvaluationResponse model validation
- ComprehensiveReportResponse model validation
- parse_llm_response() with various input formats
- Error handling for invalid inputs (JSON, validation, type errors)
"""
from __future__ import annotations

import pytest
from evaluation.schemas import (
    StageEvaluationResponse,
    ComprehensiveReportResponse,
    parse_llm_response,
)
from common.error_handling.result import Result


class TestStageEvaluationResponse:
    """Test StageEvaluationResponse Pydantic model."""

    def test_create_valid_stage_evaluation(self):
        """Test creating a valid StageEvaluationResponse."""
        # Arrange & Act
        response = StageEvaluationResponse(
            scores={"communication": 85.0, "product_knowledge": 90.0},
            strengths=["Clear communication", "Good product knowledge"],
            suggestions=["Improve closing techniques"],
            summary="Overall good performance with minor areas for improvement.",
            confidence=0.9,
        )

        # Assert
        assert response.scores["communication"] == 85.0
        assert response.scores["product_knowledge"] == 90.0
        assert len(response.strengths) == 2
        assert len(response.suggestions) == 1
        assert response.confidence == 0.9
        assert response.summary == "Overall good performance with minor areas for improvement."

    def test_stage_evaluation_defaults(self):
        """Test StageEvaluationResponse with default values."""
        # Arrange & Act
        response = StageEvaluationResponse()

        # Assert
        assert response.scores == {}
        assert response.strengths == []
        assert response.suggestions == []
        assert response.summary == ""
        assert response.confidence == 0.0

    def test_stage_evaluation_confidence_bounds(self):
        """Test confidence field bounds validation."""
        # Test valid lower bound
        response_low = StageEvaluationResponse(confidence=0.0)
        assert response_low.confidence == 0.0

        # Test valid upper bound
        response_high = StageEvaluationResponse(confidence=1.0)
        assert response_high.confidence == 1.0

        # Test invalid values (should raise ValidationError)
        with pytest.raises(Exception):  # Pydantic ValidationError
            StageEvaluationResponse(confidence=-0.1)

        with pytest.raises(Exception):  # Pydantic ValidationError
            StageEvaluationResponse(confidence=1.1)


class TestComprehensiveReportResponse:
    """Test ComprehensiveReportResponse Pydantic model."""

    def test_create_valid_comprehensive_report(self):
        """Test creating a valid ComprehensiveReportResponse."""
        # Arrange & Act
        response = ComprehensiveReportResponse(
            overall_score=85.5,
            dimension_scores={"communication": 90.0, "product_knowledge": 80.0},
            key_strengths=["Excellent communication", "Strong closing"],
            key_improvements=["Product knowledge depth"],
            recommendations=["Practice product features", "Role play objections"],
            detailed_feedback="Overall strong performance with room to improve technical knowledge.",
            stage_summaries={"stage_1": "Good opening", "stage_2": "Strong closing"},
        )

        # Assert
        assert response.overall_score == 85.5
        assert len(response.dimension_scores) == 2
        assert len(response.key_strengths) == 2
        assert len(response.key_improvements) == 1
        assert len(response.recommendations) == 2
        assert response.detailed_feedback != ""

    def test_comprehensive_report_defaults(self):
        """Test ComprehensiveReportResponse with default values."""
        # Arrange & Act - overall_score is required, others have defaults
        response = ComprehensiveReportResponse(overall_score=75.0)

        # Assert
        assert response.overall_score == 75.0
        assert response.dimension_scores == {}
        assert response.key_strengths == []
        assert response.key_improvements == []
        assert response.recommendations == []
        assert response.detailed_feedback == ""
        assert response.stage_summaries == {}

    def test_comprehensive_report_score_bounds(self):
        """Test overall_score field bounds validation."""
        # Test valid lower bound
        response_low = ComprehensiveReportResponse(overall_score=0.0)
        assert response_low.overall_score == 0.0

        # Test valid upper bound
        response_high = ComprehensiveReportResponse(overall_score=100.0)
        assert response_high.overall_score == 100.0

        # Test invalid values (should raise ValidationError)
        with pytest.raises(Exception):  # Pydantic ValidationError
            ComprehensiveReportResponse(overall_score=-0.1)

        with pytest.raises(Exception):  # Pydantic ValidationError
            ComprehensiveReportResponse(overall_score=100.1)


class TestParseLlmResponse:
    """Test parse_llm_response function."""

    @pytest.mark.asyncio
    async def test_parse_valid_json_string_stage_evaluation(self):
        """Test parsing valid JSON string for StageEvaluationResponse."""
        # Arrange
        valid_json = """{
            "scores": {"communication": 85.0, "product_knowledge": 90.0},
            "strengths": ["Clear communication"],
            "suggestions": ["Improve closing"],
            "summary": "Good performance",
            "confidence": 0.9
        }"""

        # Act
        result = await parse_llm_response(valid_json, StageEvaluationResponse)

        # Assert
        assert result.is_success
        assert result.value is not None
        assert result.value.scores["communication"] == 85.0
        assert result.value.strengths == ["Clear communication"]
        assert result.value.confidence == 0.9

    @pytest.mark.asyncio
    async def test_parse_valid_json_string_comprehensive_report(self):
        """Test parsing valid JSON string for ComprehensiveReportResponse."""
        # Arrange
        valid_json = """{
            "overall_score": 85.5,
            "dimension_scores": {"communication": 90.0},
            "key_strengths": ["Excellent"],
            "key_improvements": ["Technical"],
            "recommendations": ["Practice"],
            "detailed_feedback": "Good work",
            "stage_summaries": {"stage_1": "Opening"}
        }"""

        # Act
        result = await parse_llm_response(valid_json, ComprehensiveReportResponse)

        # Assert
        assert result.is_success
        assert result.value.overall_score == 85.5
        assert result.value.dimension_scores["communication"] == 90.0

    @pytest.mark.asyncio
    async def test_parse_dict_input(self):
        """Test parsing dict input directly."""
        # Arrange
        data = {
            "scores": {"communication": 75.0},
            "strengths": ["Good"],
            "suggestions": ["Improve"],
            "summary": "Okay",
            "confidence": 0.75,
        }

        # Act
        result = await parse_llm_response(data, StageEvaluationResponse)

        # Assert
        assert result.is_success
        assert result.value.scores["communication"] == 75.0

    @pytest.mark.asyncio
    async def test_parse_bytes_input(self):
        """Test parsing bytes input."""
        # Arrange
        json_bytes = b'{"scores": {"communication": 80.0}, "strengths": ["Good"], "suggestions": [], "summary": "Test", "confidence": 0.8}'

        # Act
        result = await parse_llm_response(json_bytes, StageEvaluationResponse)

        # Assert
        assert result.is_success
        assert result.value.scores["communication"] == 80.0

    @pytest.mark.asyncio
    async def test_parse_invalid_json_string(self):
        """Test parsing invalid JSON string."""
        # Arrange
        invalid_json = "{not valid json}"

        # Act
        result = await parse_llm_response(invalid_json, StageEvaluationResponse)

        # Assert
        assert not result.is_success
        assert "LLM_PARSE_JSON_ERROR" in result.fallback or "JSON_DECODE_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_parse_invalid_bytes(self):
        """Test parsing invalid bytes input."""
        # Arrange
        invalid_bytes = b"\x80\x81\x82\x83"  # Invalid UTF-8

        # Act
        result = await parse_llm_response(invalid_bytes, StageEvaluationResponse)

        # Assert
        assert not result.is_success
        assert "LLM_PARSE_BYTES_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_parse_unsupported_type(self):
        """Test parsing unsupported input type."""
        # Arrange
        invalid_input = 12345  # Integer not supported

        # Act
        result = await parse_llm_response(invalid_input, StageEvaluationResponse)

        # Assert
        assert not result.is_success
        assert "LLM_PARSE_TYPE_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_parse_validation_error_missing_required_field(self):
        """Test parsing with missing required field (overall_score)."""
        # Arrange
        incomplete_json = '{"dimension_scores": {}, "key_strengths": []}'

        # Act
        result = await parse_llm_response(incomplete_json, ComprehensiveReportResponse)

        # Assert
        assert not result.is_success
        assert "LLM_VALIDATION_ERROR" in result.fallback
        assert "overall_score" in result.fallback.lower()

    @pytest.mark.asyncio
    async def test_parse_validation_error_invalid_field_type(self):
        """Test parsing with invalid field type."""
        # Arrange
        invalid_type_json = '{"overall_score": "not_a_number", "dimension_scores": {}}'

        # Act
        result = await parse_llm_response(invalid_type_json, ComprehensiveReportResponse)

        # Assert
        assert not result.is_success
        assert "LLM_VALIDATION_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_parse_validation_error_out_of_range(self):
        """Test parsing with out-of-range value."""
        # Arrange
        out_of_range_json = '{"overall_score": 150.0, "dimension_scores": {}}'

        # Act
        result = await parse_llm_response(out_of_range_json, ComprehensiveReportResponse)

        # Assert
        assert not result.is_success
        assert "LLM_VALIDATION_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_parse_empty_json_object(self):
        """Test parsing empty JSON object with required fields missing."""
        # Arrange
        empty_json = "{}"

        # Act
        result = await parse_llm_response(empty_json, StageEvaluationResponse)

        # Assert - StageEvaluationResponse has all optional fields, so this should succeed
        assert result.is_success
        assert result.value.scores == {}
        assert result.value.strengths == []

    @pytest.mark.asyncio
    async def test_parse_malformed_json(self):
        """Test parsing malformed JSON."""
        # Arrange
        malformed_json = '{"scores": {"communication": 85}, "strengths": ["Good"]'  # Missing closing brace

        # Act
        result = await parse_llm_response(malformed_json, StageEvaluationResponse)

        # Assert
        assert not result.is_success
        assert "LLM_PARSE_JSON_ERROR" in result.fallback or "JSON_DECODE_ERROR" in result.fallback

    @pytest.mark.asyncio
    async def test_parse_with_extra_fields(self):
        """Test parsing JSON with extra fields (should be ignored)."""
        # Arrange
        json_with_extra = """{
            "scores": {"communication": 85.0},
            "strengths": ["Good"],
            "suggestions": [],
            "summary": "Test",
            "confidence": 0.85,
            "extra_field": "should be ignored",
            "another_extra": 123
        }"""

        # Act
        result = await parse_llm_response(json_with_extra, StageEvaluationResponse)

        # Assert
        assert result.is_success
        assert result.value.scores["communication"] == 85.0
        # Extra fields should not cause validation error (Pydantic v2 default behavior)

    @pytest.mark.asyncio
    async def test_parse_minimal_valid_stage_evaluation(self):
        """Test parsing minimal valid StageEvaluationResponse."""
        # Arrange
        minimal_json = '{"scores": {"communication": 70.0}}'

        # Act
        result = await parse_llm_response(minimal_json, StageEvaluationResponse)

        # Assert
        assert result.is_success
        assert result.value.scores == {"communication": 70.0}
        assert result.value.strengths == []
        assert result.value.suggestions == []
        assert result.value.summary == ""
        assert result.value.confidence == 0.0

    @pytest.mark.asyncio
    async def test_parse_minimal_valid_comprehensive_report(self):
        """Test parsing minimal valid ComprehensiveReportResponse."""
        # Arrange
        minimal_json = '{"overall_score": 75.0}'

        # Act
        result = await parse_llm_response(minimal_json, ComprehensiveReportResponse)

        # Assert
        assert result.is_success
        assert result.value.overall_score == 75.0
        assert result.value.dimension_scores == {}
        assert result.value.key_strengths == []

    @pytest.mark.asyncio
    async def test_parse_large_values(self):
        """Test parsing with large array values."""
        # Arrange
        large_json = """{
            "scores": {"communication": 85.0},
            "strengths": ["Good"] + ["Point"] * 100,
            "suggestions": ["Improve"] + ["Tip"] * 100,
            "summary": "Test",
            "confidence": 0.9
        }"""
        # Create actual large arrays
        import json
        large_data = {
            "scores": {"communication": 85.0},
            "strengths": ["Good"] + [f"Point {i}" for i in range(100)],
            "suggestions": ["Improve"] + [f"Tip {i}" for i in range(100)],
            "summary": "Test",
            "confidence": 0.9,
        }

        # Act
        result = await parse_llm_response(json.dumps(large_data), StageEvaluationResponse)

        # Assert
        assert result.is_success
        assert len(result.value.strengths) == 101
        assert len(result.value.suggestions) == 101

    @pytest.mark.asyncio
    async def test_parse_unicode_characters(self):
        """Test parsing JSON with unicode characters."""
        # Arrange
        unicode_json = """{
            "scores": {"communication": 85.0},
            "strengths": ["优秀的沟通能力", "Good communication 中文"],
            "suggestions": ["Improvement 建议"],
            "summary": "Performance 表现",
            "confidence": 0.9
        }"""

        # Act
        result = await parse_llm_response(unicode_json, StageEvaluationResponse)

        # Assert
        assert result.is_success
        assert "中文" in result.value.strengths[1]
        assert "建议" in result.value.suggestions[0]

    @pytest.mark.asyncio
    async def test_parse_nested_json_in_stage_summaries(self):
        """Test parsing nested JSON structures in stage_summaries."""
        # Arrange
        nested_json = """{
            "overall_score": 80.0,
            "dimension_scores": {},
            "key_strengths": [],
            "key_improvements": [],
            "recommendations": [],
            "detailed_feedback": "Good",
            "stage_summaries": {
                "stage_1": {"score": 85, "summary": "Good opening"},
                "stage_2": {"score": 75, "summary": "Okay closing"}
            }
        }"""

        # Act
        result = await parse_llm_response(nested_json, ComprehensiveReportResponse)

        # Assert
        assert result.is_success
        assert isinstance(result.value.stage_summaries, dict)
        assert "stage_1" in result.value.stage_summaries
        assert result.value.stage_summaries["stage_1"]["score"] == 85

    @pytest.mark.asyncio
    async def test_parse_zero_values(self):
        """Test parsing with zero/empty values."""
        # Arrange
        zero_json = """{
            "scores": {"communication": 0.0},
            "strengths": [],
            "suggestions": [],
            "summary": "",
            "confidence": 0.0
        }"""

        # Act
        result = await parse_llm_response(zero_json, StageEvaluationResponse)

        # Assert
        assert result.is_success
        assert result.value.scores["communication"] == 0.0
        assert result.value.confidence == 0.0
        assert result.value.summary == ""
