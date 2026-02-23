"""EmotionAnalyzer 파이프라인 단위 테스트.

실제 모델 로딩을 mock하여 빠르게 테스트.
"""

from unittest.mock import MagicMock, patch

import torch

from app.pipeline.emotion import EmotionAnalyzer, KOTE_LABELS_CLEAN


class TestEmotionAnalyzer:
    """모델을 mock하여 추론 로직만 테스트."""

    def _create_mock_analyzer(self, logits: list[float]) -> EmotionAnalyzer:
        """mock 모델을 가진 EmotionAnalyzer 생성."""
        analyzer = EmotionAnalyzer()
        analyzer.device = torch.device("cpu")
        analyzer.tokenizer = MagicMock()
        analyzer.model = MagicMock()

        # tokenizer mock
        mock_inputs = {
            "input_ids": torch.zeros(1, 10, dtype=torch.long),
            "attention_mask": torch.ones(1, 10, dtype=torch.long),
        }
        analyzer.tokenizer.return_value = mock_inputs

        # model mock: logits 반환 (sigmoid 전)
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([logits])
        analyzer.model.return_value = mock_output

        analyzer.labels = KOTE_LABELS_CLEAN
        return analyzer

    def test_analyze_returns_emotions_above_threshold(self):
        # sigmoid(2.0) ≈ 0.88, sigmoid(-2.0) ≈ 0.12
        logits = [-2.0] * 43
        logits[39] = 2.0  # 행복
        logits[41] = 1.5  # 기쁨 → sigmoid ≈ 0.82

        analyzer = self._create_mock_analyzer(logits)
        result = analyzer.analyze("테스트", top_k=5, threshold=0.3)

        assert len(result) >= 1
        labels = {e["label"] for e in result}
        assert "행복" in labels

    def test_analyze_respects_threshold(self):
        logits = [-2.0] * 43
        logits[5] = 0.0  # sigmoid(0.0) = 0.5

        analyzer = self._create_mock_analyzer(logits)

        # threshold 0.6 → 0.5는 필터링
        result = analyzer.analyze("테스트", threshold=0.6)
        assert len(result) == 0

        # threshold 0.4 → 0.5는 포함
        result = analyzer.analyze("테스트", threshold=0.4)
        assert len(result) == 1

    def test_analyze_respects_top_k(self):
        logits = [2.0] * 43  # 모든 감정 활성화
        analyzer = self._create_mock_analyzer(logits)

        result = analyzer.analyze("테스트", top_k=3, threshold=0.3)
        assert len(result) == 3

    def test_analyze_sorted_by_intensity_desc(self):
        logits = [-2.0] * 43
        logits[0] = 1.0  # 불평/불만 → sigmoid ≈ 0.73
        logits[39] = 3.0  # 행복 → sigmoid ≈ 0.95
        logits[5] = 2.0  # 슬픔 → sigmoid ≈ 0.88

        analyzer = self._create_mock_analyzer(logits)
        result = analyzer.analyze("테스트", top_k=5, threshold=0.3)

        intensities = [e["intensity"] for e in result]
        assert intensities == sorted(intensities, reverse=True)

    def test_get_dominant_emotion_returns_single(self):
        logits = [-2.0] * 43
        logits[39] = 3.0  # 행복

        analyzer = self._create_mock_analyzer(logits)
        result = analyzer.get_dominant_emotion("테스트")

        assert result is not None
        assert result["label"] == "행복"

    def test_get_dominant_emotion_none_when_no_match(self):
        logits = [-5.0] * 43  # 모든 감정 비활성

        analyzer = self._create_mock_analyzer(logits)
        result = analyzer.get_dominant_emotion("테스트")

        assert result is None

    def test_analyze_batch(self):
        logits = [-2.0] * 43
        logits[39] = 2.0

        analyzer = self._create_mock_analyzer(logits)

        # batch mock 수정: 2개 샘플
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([logits, logits])
        analyzer.model.return_value = mock_output

        results = analyzer.analyze_batch(["텍스트1", "텍스트2"], top_k=3)
        assert len(results) == 2
        assert all(isinstance(r, list) for r in results)

    def test_labels_count_matches(self):
        """KOTE 43감정 라벨 수 확인."""
        assert len(KOTE_LABELS_CLEAN) == 43
