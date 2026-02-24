"""휴먼 감지 서비스 단위 테스트."""

import pytest

from app.services.human_detection import HumanDetectionAnalyzer, HumanDetectionResult, TurnContext


@pytest.fixture
def analyzer():
    return HumanDetectionAnalyzer()


def _ctx(turn=1, prev_elapsed=None, prev_lengths=None):
    return TurnContext(
        turn_number=turn,
        previous_elapsed=prev_elapsed or [],
        previous_lengths=prev_lengths or [],
    )


class TestResponseTimeAnalysis:
    """응답 시간 분석 테스트."""

    def test_instant_long_response_high_score(self, analyzer: HumanDetectionAnalyzer):
        """0.5초에 300자 → 복사-붙여넣기 의심 (높은 점수)."""
        result = analyzer.analyze_turn(
            response_text="A" * 300,
            elapsed_seconds=0.5,
            turn_context=_ctx(),
        )
        assert result.signals["response_time"] == 25

    def test_slow_short_response_high_score(self, analyzer: HumanDetectionAnalyzer):
        """35초에 100자 → 수동 타이핑 의심."""
        result = analyzer.analyze_turn(
            response_text="A" * 100,
            elapsed_seconds=35.0,
            turn_context=_ctx(),
        )
        assert result.signals["response_time"] == 20

    def test_normal_llm_response_zero_score(self, analyzer: HumanDetectionAnalyzer):
        """5초에 200자 → 정상 LLM 범위."""
        result = analyzer.analyze_turn(
            response_text="A" * 200,
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert result.signals["response_time"] == 0


class TestTypingSpeedAnalysis:
    """타이핑 속도 분석 테스트."""

    def test_human_typing_speed(self, analyzer: HumanDetectionAnalyzer):
        """50자를 10초에 → 5 chars/sec → 사람 타이핑 속도."""
        result = analyzer.analyze_turn(
            response_text="A" * 50,
            elapsed_seconds=10.0,
            turn_context=_ctx(),
        )
        assert result.signals["typing_speed"] == 25

    def test_instant_paste_speed(self, analyzer: HumanDetectionAnalyzer):
        """1000자를 0.1초에 → 10000 chars/sec → 복사-붙여넣기."""
        result = analyzer.analyze_turn(
            response_text="A" * 1000,
            elapsed_seconds=0.1,
            turn_context=_ctx(),
        )
        assert result.signals["typing_speed"] == 15

    def test_normal_llm_speed(self, analyzer: HumanDetectionAnalyzer):
        """500자를 5초에 → 100 chars/sec → 정상 LLM."""
        result = analyzer.analyze_turn(
            response_text="A" * 500,
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert result.signals["typing_speed"] == 0


class TestConsistencyAnalysis:
    """턴 간 일관성 분석 테스트."""

    def test_insufficient_data_zero_score(self, analyzer: HumanDetectionAnalyzer):
        """이전 턴 데이터 1개 이하 → 0점."""
        result = analyzer.analyze_turn(
            response_text="A" * 200,
            elapsed_seconds=5.0,
            turn_context=_ctx(turn=2, prev_elapsed=[5.0], prev_lengths=[200]),
        )
        assert result.signals["consistency"] == 0

    def test_consistent_responses_zero_score(self, analyzer: HumanDetectionAnalyzer):
        """이전 턴들과 비슷한 응답 → 0점."""
        prev_elapsed = [5.0, 5.2, 4.8]
        prev_lengths = [200, 210, 190]
        result = analyzer.analyze_turn(
            response_text="A" * 205,
            elapsed_seconds=5.1,
            turn_context=_ctx(turn=4, prev_elapsed=prev_elapsed, prev_lengths=prev_lengths),
        )
        assert result.signals["consistency"] == 0

    def test_high_variance_increases_score(self, analyzer: HumanDetectionAnalyzer):
        """이전 턴들은 5초/200자인데 갑자기 30초/50자 → 일관성 점수 증가."""
        prev_elapsed = [5.0, 5.1, 4.9]
        prev_lengths = [200, 205, 195]
        result = analyzer.analyze_turn(
            response_text="A" * 50,
            elapsed_seconds=30.0,
            turn_context=_ctx(turn=4, prev_elapsed=prev_elapsed, prev_lengths=prev_lengths),
        )
        assert result.signals["consistency"] > 0


class TestStructureAnalysis:
    """구조적 일관성 분석 테스트."""

    def test_repeated_chars_detected(self, analyzer: HumanDetectionAnalyzer):
        """같은 문자 5+회 반복 → 구조 점수 증가."""
        result = analyzer.analyze_turn(
            response_text="이것은 테스트입니다aaaaaa 끝",
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert result.signals["structure"] >= 5

    def test_clean_text_zero_score(self, analyzer: HumanDetectionAnalyzer):
        """정상적인 텍스트 → 0점."""
        result = analyzer.analyze_turn(
            response_text="인공지능은 교육의 효율성을 크게 향상시킬 수 있습니다.",
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert result.signals["structure"] == 0


class TestColloquialAnalysis:
    """구어체 패턴 분석 테스트."""

    def test_korean_internet_expression(self, analyzer: HumanDetectionAnalyzer):
        """한국어 인터넷 표현 → 점수 증가."""
        result = analyzer.analyze_turn(
            response_text="이건 말이 안 되는 주장이에요ㅋㅋㅋ 진짜 웃긴다ㅎㅎ",
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert result.signals["colloquial"] >= 5

    def test_multiple_colloquial_patterns(self, analyzer: HumanDetectionAnalyzer):
        """여러 구어체 패턴 → 더 높은 점수."""
        result = analyzer.analyze_turn(
            response_text="ㅋㅋㅋ 이건 좀........ 아닌데???? ㅠㅠ",
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert result.signals["colloquial"] >= 10

    def test_formal_text_zero_score(self, analyzer: HumanDetectionAnalyzer):
        """격식체 텍스트 → 0점."""
        result = analyzer.analyze_turn(
            response_text="AI 기술의 발전은 교육 분야에 혁신적인 변화를 가져올 것으로 예상됩니다.",
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert result.signals["colloquial"] == 0


class TestOverallScoring:
    """종합 점수 및 레벨 판정 테스트."""

    def test_normal_ai_response(self, analyzer: HumanDetectionAnalyzer):
        """정상적인 AI 응답 → 'normal' 레벨."""
        result = analyzer.analyze_turn(
            response_text="인공지능은 교육의 개인화를 통해 학습 효율을 높일 수 있습니다. " * 5,
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert result.level == "normal"
        assert result.score <= 30

    def test_suspicious_response(self, analyzer: HumanDetectionAnalyzer):
        """느린 응답 + 짧은 텍스트 → 의심 레벨."""
        result = analyzer.analyze_turn(
            response_text="글쎄요... 잘 모르겠는데요",
            elapsed_seconds=35.0,
            turn_context=_ctx(),
        )
        # 응답시간 20 + 타이핑속도 25 = 45 → suspicious
        assert result.score > 30

    def test_high_suspicion_multiple_signals(self, analyzer: HumanDetectionAnalyzer):
        """여러 신호 동시 발생 → 높은 의심."""
        result = analyzer.analyze_turn(
            response_text="ㅋㅋㅋ 이건 좀 아닌데ㅠㅠ 진짜 웃김ㅎㅎ",
            elapsed_seconds=40.0,
            turn_context=_ctx(
                turn=5,
                prev_elapsed=[5.0, 5.1, 4.9],
                prev_lengths=[200, 205, 195],
            ),
        )
        assert result.score > 60
        assert result.level == "high_suspicion"

    def test_score_capped_at_100(self, analyzer: HumanDetectionAnalyzer):
        """모든 신호 최대치여도 100을 넘지 않음."""
        result = analyzer.analyze_turn(
            response_text="ㅋㅋㅋ ㅎㅎ ㅠㅠ !!!!! ???? ~~~~",
            elapsed_seconds=60.0,
            turn_context=_ctx(
                turn=5,
                prev_elapsed=[5.0, 5.1, 4.9],
                prev_lengths=[200, 205, 195],
            ),
        )
        assert result.score <= 100

    def test_result_contains_all_signals(self, analyzer: HumanDetectionAnalyzer):
        """결과에 5개 신호가 모두 포함되어야 함."""
        result = analyzer.analyze_turn(
            response_text="테스트 응답",
            elapsed_seconds=5.0,
            turn_context=_ctx(),
        )
        assert "response_time" in result.signals
        assert "typing_speed" in result.signals
        assert "consistency" in result.signals
        assert "structure" in result.signals
        assert "colloquial" in result.signals
