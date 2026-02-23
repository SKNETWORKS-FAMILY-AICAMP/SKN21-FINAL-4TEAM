"""EmbeddingService 파이프라인 단위 테스트.

실제 모델 로딩을 mock하여 빠르게 테스트.
"""

from unittest.mock import MagicMock

import torch

from app.pipeline.embedding import EmbeddingService, EMBEDDING_DIM


class TestEmbeddingService:
    """모델을 mock하여 임베딩 로직만 테스트."""

    def _create_mock_service(self, batch_size: int = 1) -> EmbeddingService:
        service = EmbeddingService()
        service.device = torch.device("cpu")
        service.tokenizer = MagicMock()
        service.model = MagicMock()

        # tokenizer mock
        mock_inputs = {
            "input_ids": torch.zeros(batch_size, 10, dtype=torch.long),
            "attention_mask": torch.ones(batch_size, 10, dtype=torch.long),
        }
        service.tokenizer.return_value = mock_inputs

        # model mock: last_hidden_state (batch_size, seq_len, dim)
        mock_output = MagicMock()
        mock_output.last_hidden_state = torch.randn(batch_size, 10, EMBEDDING_DIM)
        service.model.return_value = mock_output

        return service

    def test_embed_returns_correct_dimension(self):
        service = self._create_mock_service(batch_size=1)
        vec = service.embed("테스트 텍스트")

        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIM

    def test_embed_values_are_floats(self):
        service = self._create_mock_service(batch_size=1)
        vec = service.embed("텍스트")

        assert all(isinstance(v, float) for v in vec)

    def test_embed_is_normalized(self):
        """L2 정규화 확인: 벡터 크기가 약 1.0."""
        service = self._create_mock_service(batch_size=1)
        vec = service.embed("텍스트")

        norm = sum(v ** 2 for v in vec) ** 0.5
        assert abs(norm - 1.0) < 0.01

    def test_embed_batch_returns_multiple(self):
        service = self._create_mock_service(batch_size=3)
        texts = ["텍스트1", "텍스트2", "텍스트3"]
        vecs = service.embed_batch(texts)

        assert len(vecs) == 3
        assert all(len(v) == EMBEDDING_DIM for v in vecs)

    def test_embed_batch_all_normalized(self):
        service = self._create_mock_service(batch_size=2)
        vecs = service.embed_batch(["a", "b"])

        for vec in vecs:
            norm = sum(v ** 2 for v in vec) ** 0.5
            assert abs(norm - 1.0) < 0.01

    def test_similarity_returns_float(self):
        service = self._create_mock_service(batch_size=2)
        score = service.similarity("텍스트A", "텍스트B")

        assert isinstance(score, float)
        assert -1.0 <= score <= 1.0

    def test_embedding_dim_is_1024(self):
        assert EMBEDDING_DIM == 1024
