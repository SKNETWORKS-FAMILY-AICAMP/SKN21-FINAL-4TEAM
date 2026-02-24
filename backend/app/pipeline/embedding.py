import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    import torch
    from transformers import AutoModel, AutoTokenizer

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("torch/transformers not installed — EmbeddingService will return fallback results")

DEFAULT_MODEL_NAME = "BAAI/bge-m3"
EMBEDDING_DIM = 1024


class EmbeddingService:
    """BGE-M3 1024차원 임베딩."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, device: str | None = None):
        self.model_name = model_name
        self.device_name = device
        self.model = None
        self.tokenizer = None
        self.device = None

    def load_model(self) -> None:
        """BGE-M3 모델과 토크나이저를 GPU/CPU에 로드."""
        if self.model is not None:
            return
        if not TORCH_AVAILABLE:
            logger.warning("Cannot load EmbeddingService — torch not installed")
            return
        logger.info("Loading EmbeddingService model: %s", self.model_name)
        try:
            if self.device_name:
                self.device = torch.device(self.device_name)
            else:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()

            logger.info("EmbeddingService loaded on %s (dim=%d)", self.device, EMBEDDING_DIM)
        except Exception as e:
            logger.warning("EmbeddingService model load failed — fallback to zero vectors: %s", e)
            self.model = None
            self.tokenizer = None

    def _ensure_loaded(self) -> bool:
        """모델 미로드 시 자동 로드 (lazy initialization). 로드 성공 시 True."""
        if self.model is None:
            self.load_model()
        return self.model is not None

    def embed(self, text: str) -> list[float]:
        """텍스트 → 1024차원 벡터. torch 미설치 시 영벡터 반환."""
        result = self.embed_batch([text])
        return result[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """배치 임베딩. BGE-M3 dense embedding 사용."""
        if not self._ensure_loaded():
            return [[0.0] * EMBEDDING_DIM for _ in texts]

        # BGE-M3 권장: 검색용 query에는 "Represent this sentence: " 프리픽스
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=8192,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            # CLS 토큰의 hidden state를 사용 (dense embedding)
            embeddings = outputs.last_hidden_state[:, 0, :]
            # L2 정규화
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().tolist()

    def similarity(self, text_a: str, text_b: str) -> float:
        """두 텍스트 간 코사인 유사도."""
        if not TORCH_AVAILABLE:
            return 0.0
        vecs = self.embed_batch([text_a, text_b])
        a = torch.tensor(vecs[0])
        b = torch.tensor(vecs[1])
        return torch.nn.functional.cosine_similarity(a.unsqueeze(0), b.unsqueeze(0)).item()


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """싱글턴 EmbeddingService 인스턴스. 모델 로드는 첫 사용 시 lazy로 수행."""
    return EmbeddingService()
