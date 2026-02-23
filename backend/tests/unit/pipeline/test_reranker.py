"""Reranker 파이프라인 단위 테스트.

실제 모델 로딩을 mock하여 빠르게 테스트.
"""

from unittest.mock import MagicMock

import torch

from app.pipeline.reranker import Reranker


class TestReranker:
    """모델을 mock하여 리랭킹 로직만 테스트."""

    def _create_mock_reranker(self, scores: list[float]) -> Reranker:
        reranker = Reranker()
        reranker.device = torch.device("cpu")
        reranker.tokenizer = MagicMock()
        reranker.model = MagicMock()

        # tokenizer mock
        n = len(scores)
        mock_inputs = {
            "input_ids": torch.zeros(n, 20, dtype=torch.long),
            "attention_mask": torch.ones(n, 20, dtype=torch.long),
        }
        reranker.tokenizer.return_value = mock_inputs

        # model mock: logits → sigmoid(score)
        # scores를 logits로 역변환할 필요 없이, 직접 logits 사용
        mock_output = MagicMock()
        mock_output.logits = torch.tensor(scores).unsqueeze(-1)
        reranker.model.return_value = mock_output

        return reranker

    def test_rerank_returns_sorted_by_score_desc(self):
        # logits: sigmoid(0) ≈ 0.5, sigmoid(2) ≈ 0.88, sigmoid(-2) ≈ 0.12
        reranker = self._create_mock_reranker([0.0, 2.0, -2.0])
        docs = ["문서A", "문서B", "문서C"]

        result = reranker.rerank("쿼리", docs, top_k=3)

        assert len(result) == 3
        assert result[0]["score"] >= result[1]["score"] >= result[2]["score"]
        # 가장 높은 점수: 문서B (index 1)
        assert result[0]["index"] == 1

    def test_rerank_respects_top_k(self):
        reranker = self._create_mock_reranker([1.0, 2.0, 0.5, -1.0, 3.0])
        docs = ["A", "B", "C", "D", "E"]

        result = reranker.rerank("쿼리", docs, top_k=2)
        assert len(result) == 2

    def test_rerank_preserves_text(self):
        reranker = self._create_mock_reranker([1.0, 0.5])
        docs = ["첫 번째 문서", "두 번째 문서"]

        result = reranker.rerank("쿼리", docs, top_k=2)
        texts = {r["text"] for r in result}
        assert "첫 번째 문서" in texts
        assert "두 번째 문서" in texts

    def test_rerank_preserves_original_index(self):
        reranker = self._create_mock_reranker([0.0, 3.0])
        docs = ["낮은 점수", "높은 점수"]

        result = reranker.rerank("쿼리", docs, top_k=2)
        # 높은 점수 문서가 먼저
        assert result[0]["index"] == 1
        assert result[0]["text"] == "높은 점수"

    def test_rerank_empty_documents(self):
        reranker = self._create_mock_reranker([])
        result = reranker.rerank("쿼리", [], top_k=5)
        assert result == []

    def test_score_pair_returns_float(self):
        reranker = self._create_mock_reranker([1.5])
        score = reranker.score_pair("쿼리", "문서")

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_rerank_single_document(self):
        reranker = self._create_mock_reranker([2.0])
        result = reranker.rerank("쿼리", ["유일한 문서"], top_k=1)

        assert len(result) == 1
        assert result[0]["text"] == "유일한 문서"
        assert result[0]["index"] == 0

    def test_rerank_score_is_between_0_and_1(self):
        """sigmoid 출력이므로 0~1 범위."""
        reranker = self._create_mock_reranker([5.0, -5.0, 0.0])
        docs = ["A", "B", "C"]

        result = reranker.rerank("쿼리", docs, top_k=3)
        for item in result:
            assert 0.0 <= item["score"] <= 1.0
