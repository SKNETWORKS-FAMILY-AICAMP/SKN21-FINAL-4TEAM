"""오케스트레이터 단위 테스트. ELO 계산, 점수 판정 로직."""

import pytest

from app.services.debate_orchestrator import calculate_elo


class TestEloCalculation:
    def test_equal_rating_a_wins(self):
        """동일 레이팅에서 A 승리 시 A 증가, B 감소."""
        new_a, new_b = calculate_elo(1500, 1500, "a_win", k=32)
        assert new_a > 1500
        assert new_b < 1500
        assert new_a + new_b == 3000  # 총합 보존

    def test_equal_rating_b_wins(self):
        """동일 레이팅에서 B 승리."""
        new_a, new_b = calculate_elo(1500, 1500, "b_win", k=32)
        assert new_a < 1500
        assert new_b > 1500

    def test_equal_rating_draw(self):
        """동일 레이팅에서 무승부면 변동 없음."""
        new_a, new_b = calculate_elo(1500, 1500, "draw", k=32)
        assert new_a == 1500
        assert new_b == 1500

    def test_underdog_wins_gains_more(self):
        """약자(낮은 ELO)가 강자를 이기면 더 많은 ELO를 획득한다."""
        # 약자 A(1200)가 강자 B(1800)를 이김
        new_a, new_b = calculate_elo(1200, 1800, "a_win", k=32)
        gain_a = new_a - 1200
        # 동일 레이팅에서의 승리 대비 더 큰 변동
        equal_a, _ = calculate_elo(1500, 1500, "a_win", k=32)
        equal_gain = equal_a - 1500
        assert gain_a > equal_gain

    def test_favorite_wins_gains_less(self):
        """강자(높은 ELO)가 약자를 이기면 적은 ELO를 획득한다."""
        new_a, new_b = calculate_elo(1800, 1200, "a_win", k=32)
        gain_a = new_a - 1800
        equal_a, _ = calculate_elo(1500, 1500, "a_win", k=32)
        equal_gain = equal_a - 1500
        assert gain_a < equal_gain

    def test_k_factor_affects_magnitude(self):
        """K 값이 클수록 변동폭이 크다."""
        new_a_16, _ = calculate_elo(1500, 1500, "a_win", k=16)
        new_a_32, _ = calculate_elo(1500, 1500, "a_win", k=32)
        assert abs(new_a_32 - 1500) > abs(new_a_16 - 1500)

    def test_elo_sum_preserved(self):
        """ELO 합계는 항상 보존된다."""
        for result in ("a_win", "b_win", "draw"):
            new_a, new_b = calculate_elo(1600, 1400, result, k=32)
            assert new_a + new_b == 3000

    def test_extreme_rating_difference(self):
        """극단적 레이팅 차이에서도 동작한다."""
        new_a, new_b = calculate_elo(2800, 800, "b_win", k=32)
        assert new_b > 800
        assert new_a < 2800
        # 약자 승리이므로 큰 변동
        assert new_b - 800 > 25
