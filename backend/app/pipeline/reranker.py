import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("torch/transformers not installed — Reranker will return fallback results")

DEFAULT_MODEL_NAME = "BAAI/bge-reranker-v2-m3"


class Reranker:
    """bge-reranker-v2-m3 기반 cross-encoder 리랭킹."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, device: str | None = None):
        self.model_name = model_name
        self.device_name = device
        self.model = None
        self.tokenizer = None
        self.device = None

    def load_model(self) -> None:
        """bge-reranker-v2-m3 모델과 토크나이저를 GPU/CPU에 로드."""
        if self.model is not None:
            return
        if not TORCH_AVAILABLE:
            logger.warning("Cannot load Reranker — torch not installed")
            return
        logger.info("Loading Reranker model: %s", self.model_name)

        if self.device_name:
            self.device = torch.device(self.device_name)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()

        logger.info("Reranker loaded on %s", self.device)

    def _ensure_loaded(self) -> bool:
        """모델 미로드 시 자동 로드 (lazy initialization). 로드 성공 시 True."""
        if self.model is None:
            self.load_model()
        return self.model is not None

    def rerank(self, query: str, documents: list[str], top_k: int = 5) -> list[dict]:
        """문서 리랭킹 → [{"index": 0, "score": 0.95, "text": "..."}, ...]

        Cross-encoder 방식: (query, document) 쌍을 모델에 입력하여 관련도 점수 산출.
        """
        if not documents:
            return []

        if not self._ensure_loaded():
            return [{"index": i, "score": 0.0, "text": doc} for i, doc in enumerate(documents[:top_k])]

        # (query, document) 쌍 생성
        pairs = [[query, doc] for doc in documents]

        inputs = self.tokenizer(
            pairs,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            # Reranker는 단일 점수 출력 (logits[:, 0] 또는 sigmoid)
            scores = torch.sigmoid(outputs.logits.squeeze(-1)).cpu().tolist()

        # 단일 문서인 경우 리스트로 감싸기
        if isinstance(scores, float):
            scores = [scores]

        # 점수 기준 내림차순 정렬
        scored_docs = [
            {"index": idx, "score": round(score, 4), "text": doc}
            for idx, (doc, score) in enumerate(zip(documents, scores, strict=False))
        ]
        scored_docs.sort(key=lambda x: x["score"], reverse=True)

        return scored_docs[:top_k]

    def score_pair(self, query: str, document: str) -> float:
        """단일 (query, document) 쌍의 관련도 점수."""
        result = self.rerank(query, [document], top_k=1)
        return result[0]["score"] if result else 0.0


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    """싱글턴 Reranker 인스턴스. 모델 로드는 첫 사용 시 lazy로 수행."""
    return Reranker()
