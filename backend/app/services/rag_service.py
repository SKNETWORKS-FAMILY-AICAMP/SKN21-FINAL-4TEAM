from sqlalchemy.ext.asyncio import AsyncSession


class RAGService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve(self, query: str, webtoon_id: str | None = None, top_k: int = 5) -> list[dict]:
        """하이브리드 검색: pgvector 벡터 유사도 + 키워드 매칭."""
        raise NotImplementedError

    async def build_evidence_bundle(self, query: str, webtoon_id: str | None, persona_id: str | None) -> dict:
        """근거 번들 구성: 에피소드 임베딩 + 로어북 + 감정 신호 + 댓글 통계."""
        raise NotImplementedError
