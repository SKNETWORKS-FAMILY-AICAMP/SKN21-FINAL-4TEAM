class EmbeddingService:
    """BGE-M3 1024차원 임베딩."""

    def __init__(self):
        self.model = None

    async def load_model(self):
        raise NotImplementedError

    async def embed(self, text: str) -> list[float]:
        """텍스트 → 1024차원 벡터."""
        raise NotImplementedError

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """배치 임베딩."""
        raise NotImplementedError
