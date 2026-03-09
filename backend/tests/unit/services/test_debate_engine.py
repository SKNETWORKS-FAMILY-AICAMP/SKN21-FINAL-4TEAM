"""토론 엔진 단위 테스트. JSON 스키마 검증, 벌점 감지 로직."""

import json

import pytest

from app.services.debate_engine import (
    detect_repetition,
    validate_response_schema,
)


class TestResponseSchemaValidation:
    def test_valid_response(self):
        """유효한 JSON 응답을 파싱한다."""
        response = json.dumps({
            "action": "argue",
            "claim": "AI will transform education.",
            "evidence": "Studies show 30% improvement.",
            "tool_used": None,
            "tool_result": None,
        })
        result = validate_response_schema(response)
        assert result is not None
        assert result["action"] == "argue"
        assert result["claim"] == "AI will transform education."

    def test_valid_response_in_code_block(self):
        """코드 블록 안의 JSON도 파싱한다."""
        response = '```json\n{"action": "rebut", "claim": "That is incorrect."}\n```'
        result = validate_response_schema(response)
        assert result is not None
        assert result["action"] == "rebut"

    def test_invalid_json(self):
        """잘못된 JSON은 None을 반환한다."""
        result = validate_response_schema("This is not JSON at all.")
        assert result is None

    def test_missing_required_fields(self):
        """필수 필드가 없으면 None을 반환한다."""
        response = json.dumps({"action": "argue"})  # claim 누락
        result = validate_response_schema(response)
        assert result is None

    def test_invalid_action(self):
        """잘못된 action 값은 None을 반환한다."""
        response = json.dumps({"action": "attack", "claim": "test"})
        result = validate_response_schema(response)
        assert result is None

    def test_all_valid_actions(self):
        """모든 유효한 action이 통과한다."""
        for action in ("argue", "rebut", "concede", "question", "summarize"):
            response = json.dumps({"action": action, "claim": "test"})
            result = validate_response_schema(response)
            assert result is not None


class TestRepetitionDetection:
    def test_no_repetition(self):
        """중복 없는 경우 False."""
        assert detect_repetition("New and unique argument", ["Previous argument"]) is False

    def test_exact_repetition(self):
        """동일한 문장은 반복으로 감지."""
        assert detect_repetition("Same argument here", ["Same argument here"]) is True

    def test_high_overlap_detected(self):
        """70% 이상 단어 중복은 반복으로 감지."""
        assert detect_repetition(
            "AI will definitely improve education significantly",
            ["AI will definitely improve education outcomes"],
        ) is True

    def test_empty_history(self):
        """이전 주장이 없으면 반복 아님."""
        assert detect_repetition("Any claim", []) is False

    def test_low_overlap_not_detected(self):
        """낮은 중복은 반복이 아님."""
        assert detect_repetition(
            "Completely different topic about space",
            ["AI and machine learning discussion"],
        ) is False


class TestLocalAgentRouting:
    """local 에이전트 관련 엔진 로직 테스트."""

    def test_valid_local_actions_accepted(self):
        """local 에이전트 응답의 유효한 action은 통과한다."""
        for action in ("argue", "rebut", "concede", "question", "summarize"):
            response = json.dumps({"action": action, "claim": "local test"})
            result = validate_response_schema(response)
            assert result is not None
            assert result["action"] == action

    def test_repetition_detection_applies_to_local(self):
        """local 에이전트 응답에도 동어반복 감지가 적용된다."""
        assert detect_repetition("Same argument again", ["Same argument again"]) is True
