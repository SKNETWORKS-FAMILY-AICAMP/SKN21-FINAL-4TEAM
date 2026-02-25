"""오케스트레이터 단위 테스트. ELO 계산, 점수 판정 로직."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.debate_orchestrator import DebateOrchestrator, calculate_elo


class TestEloCalculation:
    def test_equal_rating_a_wins(self):
        """동일 레이팅에서 A 승리 시 A 증가, B 감소.
        비대칭 K-factor(k_win=40, k_loss=24) 사용 → ELO 합 보존 안 됨."""
        new_a, new_b = calculate_elo(1500, 1500, "a_win")
        assert new_a > 1500          # A는 증가
        assert new_b < 1500          # B는 감소
        assert new_a - 1500 > 1500 - new_b  # 승자 증가폭 > 패자 감소폭 (비대칭)

    def test_equal_rating_b_wins(self):
        """동일 레이팅에서 B 승리."""
        new_a, new_b = calculate_elo(1500, 1500, "b_win")
        assert new_a < 1500
        assert new_b > 1500
        assert new_b - 1500 > 1500 - new_a  # 승자 증가폭 > 패자 감소폭 (비대칭)

    def test_equal_rating_draw(self):
        """동일 레이팅에서 무승부면 변동 없음 (대칭 k_draw 사용)."""
        new_a, new_b = calculate_elo(1500, 1500, "draw")
        assert new_a == 1500
        assert new_b == 1500

    def test_asymmetric_k_winner_gains_more_than_loser_loses(self):
        """비대칭 K-factor: 승자의 ELO 증가폭이 패자의 감소폭보다 크다."""
        # k_win=40 > k_loss=24 이므로 동일 기대값 기준에서 승자 이득 > 패자 손실
        new_a, new_b = calculate_elo(1500, 1500, "a_win")
        gain_a = new_a - 1500   # 승자 증가 (k_win=40 적용)
        loss_b = 1500 - new_b   # 패자 감소 (k_loss=24 적용)
        assert gain_a > loss_b

    def test_underdog_wins_gains_more(self):
        """약자(낮은 ELO)가 강자를 이기면 더 많은 ELO를 획득한다."""
        new_a_underdog, _ = calculate_elo(1200, 1800, "a_win")
        new_a_equal, _ = calculate_elo(1500, 1500, "a_win")
        gain_underdog = new_a_underdog - 1200
        gain_equal = new_a_equal - 1500
        assert gain_underdog > gain_equal

    def test_favorite_wins_gains_less(self):
        """강자(높은 ELO)가 약자를 이기면 적은 ELO를 획득한다."""
        new_a_favorite, _ = calculate_elo(1800, 1200, "a_win")
        new_a_equal, _ = calculate_elo(1500, 1500, "a_win")
        gain_favorite = new_a_favorite - 1800
        gain_equal = new_a_equal - 1500
        assert gain_favorite < gain_equal

    def test_draw_preserves_elo_sum(self):
        """무승부는 k_draw 대칭 적용 → ELO 합이 보존된다."""
        new_a, new_b = calculate_elo(1600, 1400, "draw")
        assert new_a + new_b == 3000

    def test_win_loss_does_not_preserve_elo_sum(self):
        """승패는 비대칭 K-factor로 인해 ELO 합이 보존되지 않는다 (설계된 동작)."""
        new_a, new_b = calculate_elo(1500, 1500, "a_win")
        # k_win(40) != k_loss(24) → 합 != 3000
        assert new_a + new_b != 3000

    def test_extreme_rating_difference(self):
        """극단적 레이팅 차이에서도 동작한다."""
        new_a, new_b = calculate_elo(2800, 800, "b_win")
        assert new_b > 800
        assert new_a < 2800
        # 약자 승리이므로 큰 변동
        assert new_b - 800 > 25


class TestJudge:
    """DebateOrchestrator.judge() — LLM 판정·스코어 계산·폴백 로직."""

    def _make_match(self, penalty_a: int = 0, penalty_b: int = 0,
                    agent_a_id: str = "aaa", agent_b_id: str = "bbb") -> MagicMock:
        match = MagicMock()
        match.agent_a_id = agent_a_id
        match.agent_b_id = agent_b_id
        match.penalty_a = penalty_a
        match.penalty_b = penalty_b
        return match

    def _make_topic(self, title: str = "AI 토론", description: str = "테스트") -> MagicMock:
        topic = MagicMock()
        topic.title = title
        topic.description = description
        return topic

    def _scorecard(self, a_logic=25, a_evidence=20, a_rebuttal=22, a_relevance=17,
                   b_logic=18, b_evidence=16, b_rebuttal=15, b_relevance=14,
                   reasoning="판정 결과") -> str:
        return json.dumps({
            "agent_a": {"logic": a_logic, "evidence": a_evidence,
                        "rebuttal": a_rebuttal, "relevance": a_relevance},
            "agent_b": {"logic": b_logic, "evidence": b_evidence,
                        "rebuttal": b_rebuttal, "relevance": b_relevance},
            "reasoning": reasoning,
        })

    @pytest.mark.asyncio
    async def test_judge_a_wins_when_diff_gte_5(self):
        """A 점수가 B보다 5 이상 높으면 A가 승자."""
        orch = DebateOrchestrator()
        # A=84, B=63 → diff=21 ≥ 5
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard()}
        )
        result = await orch.judge(self._make_match(), [], self._make_topic())

        assert result["winner_id"] == "aaa"
        assert result["score_a"] == 84
        assert result["score_b"] == 63

    @pytest.mark.asyncio
    async def test_judge_b_wins_when_b_score_higher(self):
        """B 점수가 A보다 5 이상 높으면 B가 승자."""
        orch = DebateOrchestrator()
        # A=49, B=84 → B wins
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard(
                a_logic=15, a_evidence=12, a_rebuttal=12, a_relevance=10,
                b_logic=25, b_evidence=20, b_rebuttal=22, b_relevance=17,
            )}
        )
        result = await orch.judge(self._make_match(), [], self._make_topic())

        assert result["winner_id"] == "bbb"
        assert result["score_b"] > result["score_a"]

    @pytest.mark.asyncio
    async def test_judge_draw_when_diff_lt_5(self):
        """점수차 5 미만이면 무승부 (winner_id=None)."""
        orch = DebateOrchestrator()
        # A=80, B=78 → diff=2 < 5 → draw
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard(
                a_logic=22, a_evidence=20, a_rebuttal=20, a_relevance=18,
                b_logic=20, b_evidence=20, b_rebuttal=20, b_relevance=18,
            )}
        )
        result = await orch.judge(self._make_match(), [], self._make_topic())

        assert result["winner_id"] is None
        assert abs(result["score_a"] - result["score_b"]) < 5

    @pytest.mark.asyncio
    async def test_judge_exact_5_diff_is_not_draw(self):
        """점수차가 정확히 5이면 무승부가 아닌 승/패로 처리된다."""
        orch = DebateOrchestrator()
        # A=84, B=79 → diff=5 → A wins (not draw)
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard(
                a_logic=25, a_evidence=20, a_rebuttal=22, a_relevance=17,
                b_logic=22, b_evidence=19, b_rebuttal=21, b_relevance=17,
            )}
        )
        result = await orch.judge(self._make_match(), [], self._make_topic())

        assert result["score_a"] - result["score_b"] == 5
        assert result["winner_id"] == "aaa"

    @pytest.mark.asyncio
    async def test_judge_fallback_on_invalid_json(self):
        """LLM이 잘못된 JSON을 반환하면 균등 점수 폴백으로 무승부 처리."""
        orch = DebateOrchestrator()
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": "이것은 JSON이 아닙니다"}
        )
        result = await orch.judge(self._make_match(), [], self._make_topic())

        assert result["winner_id"] is None
        assert result["score_a"] == result["score_b"]
        assert "오류" in result["scorecard"]["reasoning"]

    @pytest.mark.asyncio
    async def test_judge_fallback_on_missing_scorecard_keys(self):
        """scorecard 내 agent_a/agent_b 키가 없으면 폴백 처리."""
        orch = DebateOrchestrator()
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": '{"invalid": "structure"}'}
        )
        result = await orch.judge(self._make_match(), [], self._make_topic())

        assert result["winner_id"] is None

    @pytest.mark.asyncio
    async def test_judge_penalty_reduces_final_score(self):
        """벌점이 기본 점수에서 차감되어 최종 점수에 반영된다."""
        orch = DebateOrchestrator()
        # A=84 - penalty_a(10) = 74, B=63 → diff=11 ≥ 5 → A wins
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard()}
        )
        result = await orch.judge(self._make_match(penalty_a=10), [], self._make_topic())

        assert result["score_a"] == 74
        assert result["penalty_a"] == 10
        assert result["winner_id"] == "aaa"

    @pytest.mark.asyncio
    async def test_judge_penalty_flips_winner(self):
        """벌점이 충분히 크면 원래 승자가 패자로 뒤집힐 수 있다."""
        orch = DebateOrchestrator()
        # A=84, B=63, penalty_a=30 → final_a=54, final_b=63 → diff=9 ≥ 5 → B wins
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard()}
        )
        result = await orch.judge(self._make_match(penalty_a=30), [], self._make_topic())

        assert result["score_a"] == 54
        assert result["winner_id"] == "bbb"

    @pytest.mark.asyncio
    async def test_judge_penalty_causes_draw(self):
        """벌점으로 점수차가 5 미만이 되면 무승부로 처리된다."""
        orch = DebateOrchestrator()
        # A=84, B=63, penalty_a=20 → final_a=64, final_b=63 → diff=1 < 5 → draw
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard()}
        )
        result = await orch.judge(self._make_match(penalty_a=20), [], self._make_topic())

        assert result["score_a"] == 64
        assert result["winner_id"] is None

    @pytest.mark.asyncio
    async def test_judge_score_capped_at_zero_with_large_penalty(self):
        """벌점이 점수를 초과하면 최종 점수는 0으로 제한된다."""
        orch = DebateOrchestrator()
        # A=84, penalty_a=100 → max(0, -16) = 0, B=63 → B wins
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard()}
        )
        result = await orch.judge(self._make_match(penalty_a=100), [], self._make_topic())

        assert result["score_a"] == 0
        assert result["winner_id"] == "bbb"

    @pytest.mark.asyncio
    async def test_judge_handles_markdown_wrapped_json(self):
        """LLM이 마크다운 코드블록으로 감싼 JSON을 반환해도 정상 파싱된다."""
        orch = DebateOrchestrator()
        raw = self._scorecard()
        wrapped = f"```json\n{raw}\n```"
        orch.client._call_openai_byok = AsyncMock(return_value={"content": wrapped})

        result = await orch.judge(self._make_match(), [], self._make_topic())

        assert result["winner_id"] == "aaa"
        assert result["score_a"] == 84

    @pytest.mark.asyncio
    async def test_judge_returns_penalty_info(self):
        """결과에 penalty_a·penalty_b 정보가 포함된다."""
        orch = DebateOrchestrator()
        orch.client._call_openai_byok = AsyncMock(
            return_value={"content": self._scorecard()}
        )
        result = await orch.judge(self._make_match(penalty_a=5, penalty_b=3), [], self._make_topic())

        assert result["penalty_a"] == 5
        assert result["penalty_b"] == 3
        assert result["score_a"] == 79   # 84 - 5
        assert result["score_b"] == 60   # 63 - 3
