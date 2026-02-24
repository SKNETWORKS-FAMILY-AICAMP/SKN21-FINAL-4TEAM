"""로컬 에이전트 응답의 휴먼 여부를 다층으로 분석하는 서비스.

AI vs AI 토론 플랫폼에서 사람이 turn_response를 수동 작성하여
AI인 척 참가하는 것을 감지하기 위한 다층 휴먼 감지 시스템.
"""

import re
import statistics
from dataclasses import dataclass, field


@dataclass
class TurnContext:
    """현재 턴의 분석에 필요한 이전 턴 문맥."""

    turn_number: int
    previous_elapsed: list[float] = field(default_factory=list)
    previous_lengths: list[int] = field(default_factory=list)


@dataclass
class HumanDetectionResult:
    """휴먼 감지 분석 결과."""

    score: int  # 0~100 종합 의심 점수
    signals: dict[str, int]  # 각 신호별 점수
    level: str  # "normal" | "suspicious" | "high_suspicion"


# 구어체/인터넷 표현 패턴
_COLLOQUIAL_PATTERNS = [
    re.compile(r"[ㅋㅎㅠㅜ]{2,}"),  # ㅋㅋ, ㅎㅎ, ㅠㅠ, ㅜㅜ
    re.compile(r"[ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ]{2,}"),  # ㄱㄱ, ㄴㄴ 등
    re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]"),  # 이모지
    re.compile(r"\.{4,}"),  # 과다한 마침표
    re.compile(r"!{3,}"),  # 과다한 느낌표
    re.compile(r"\?{3,}"),  # 과다한 물음표
    re.compile(r"[~]{3,}"),  # 과다한 물결표
]

# 오타/비정형 패턴
_TYPO_PATTERNS = [
    re.compile(r"(.)\1{4,}"),  # 같은 문자 5회 이상 반복
    re.compile(r"\s{3,}"),  # 과다한 연속 공백
]


class HumanDetectionAnalyzer:
    """로컬 에이전트 응답의 휴먼 여부를 다층으로 분석."""

    def analyze_turn(
        self,
        response_text: str,
        elapsed_seconds: float,
        turn_context: TurnContext,
    ) -> HumanDetectionResult:
        """여러 신호를 종합해 suspicion_score (0~100) 반환."""
        claim_length = len(response_text)

        signals: dict[str, int] = {}
        signals["response_time"] = self._analyze_response_time(elapsed_seconds, claim_length)
        signals["typing_speed"] = self._analyze_typing_speed(elapsed_seconds, claim_length)
        signals["consistency"] = self._analyze_consistency(
            elapsed_seconds,
            claim_length,
            turn_context.previous_elapsed,
            turn_context.previous_lengths,
        )
        signals["structure"] = self._analyze_structure(response_text)
        signals["colloquial"] = self._analyze_colloquial(response_text)

        total = sum(signals.values())
        # 0~100 범위로 클램핑
        total = max(0, min(100, total))

        if total <= 30:
            level = "normal"
        elif total <= 60:
            level = "suspicious"
        else:
            level = "high_suspicion"

        return HumanDetectionResult(score=total, signals=signals, level=level)

    def _analyze_response_time(self, elapsed_sec: float, claim_length: int) -> int:
        """응답 시간 분석. LLM은 토큰 생성에 일정 시간 소요."""
        # 매우 빠른 응답에 긴 텍스트 → 복사-붙여넣기 의심
        if elapsed_sec < 1.0 and claim_length > 200:
            return 25

        # 너무 느린 응답에 짧은 텍스트 → 수동 타이핑 의심
        if elapsed_sec > 30 and claim_length < 200:
            return 20

        # 극단적으로 느린 응답
        if elapsed_sec > 60 and claim_length < 500:
            return 15

        # LLM 일반 범위: 2~20초. 범위 밖이면 비례 점수
        if elapsed_sec < 2.0 and claim_length > 100:
            return 10

        return 0

    def _analyze_typing_speed(self, elapsed_sec: float, claim_length: int) -> int:
        """타이핑 속도 비율 분석. LLM은 일정한 속도, 사람은 극단적."""
        if elapsed_sec <= 0.1:
            # 사실상 즉시 응답 — 프리캐싱이거나 복사-붙여넣기
            if claim_length > 50:
                return 15
            return 0

        chars_per_sec = claim_length / elapsed_sec

        # 사람 타이핑 속도 (한국어 ~3~8 chars/sec)
        if chars_per_sec < 15:
            return 25

        # 복사-붙여넣기 수준 (즉시 전송)
        if chars_per_sec > 5000:
            return 15

        return 0

    def _analyze_consistency(
        self,
        elapsed: float,
        length: int,
        prev_elapsed: list[float],
        prev_lengths: list[int],
    ) -> int:
        """턴 간 일관성 분석. LLM은 비교적 일관, 사람은 편차가 큼."""
        if len(prev_elapsed) < 2:
            return 0  # 데이터 부족

        score = 0

        # 응답 시간 편차
        mean_elapsed = statistics.mean(prev_elapsed)
        stdev_elapsed = statistics.stdev(prev_elapsed) if len(prev_elapsed) >= 2 else 0
        if stdev_elapsed > 0:
            z_elapsed = abs(elapsed - mean_elapsed) / stdev_elapsed
            if z_elapsed > 3.0:
                score += 12
            elif z_elapsed > 2.0:
                score += 6

        # 응답 길이 편차
        mean_length = statistics.mean(prev_lengths)
        stdev_length = statistics.stdev(prev_lengths) if len(prev_lengths) >= 2 else 0
        if stdev_length > 0:
            z_length = abs(length - mean_length) / stdev_length
            if z_length > 3.0:
                score += 8
            elif z_length > 2.0:
                score += 4

        return min(score, 20)

    def _analyze_structure(self, text: str) -> int:
        """구조적 일관성 분석. 오타, 비표준 공백/줄바꿈 패턴."""
        score = 0

        for pattern in _TYPO_PATTERNS:
            if pattern.search(text):
                score += 5

        # 불완전한 문장 (갑작스런 중단 — 조사/접속사로 끝남)
        stripped = text.rstrip()
        if stripped and stripped[-1] in ("은", "는", "이", "가", "을", "를", "에", "의", "와", "과"):
            score += 5

        return min(score, 15)

    def _analyze_colloquial(self, text: str) -> int:
        """한국어 구어체/인터넷 표현 감지. LLM은 거의 사용하지 않음."""
        score = 0
        matches = 0

        for pattern in _COLLOQUIAL_PATTERNS:
            if pattern.search(text):
                matches += 1

        if matches >= 3:
            score = 15
        elif matches >= 2:
            score = 10
        elif matches >= 1:
            score = 5

        return min(score, 15)
