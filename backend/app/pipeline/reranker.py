class Reranker:
    """bge-reranker-v2-m3 기반 리랭킹."""

    def __init__(self):
        self.model = None

    async def load_model(self):
        raise NotImplementedError

    async def rerank(self, query: str, documents: list[str], top_k: int = 5) -> list[dict]:
        """문서 리랭킹 → [{"index": 0, "score": 0.95, "text": "..."}, ...]"""
        raise NotImplementedError
