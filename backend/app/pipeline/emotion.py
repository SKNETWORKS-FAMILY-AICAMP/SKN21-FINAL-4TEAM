import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("torch/transformers not installed — EmotionAnalyzer will return fallback results")

# KOTE 43감정 라벨 (한국어 감정 분류 데이터셋)
KOTE_LABELS = [
    "불평/불만",
    "환영/호의",
    "감동/감사",
    "지긋지긋",
    "고마운",
    "슬픔",
    "화남/분노",
    "존경",
    "기대감",
    "우쭐댐/으시댐",
    "안타까움/실망",
    "비장함",
    "의심/불신",
    "뿌듯함",
    "편안/쾌ستان",
    "신기함/관심",
    "아껴주는",
    "부끄러움",
    "공포/무서움",
    "절망",
    "한심함",
    "역겨운/징그러운",
    "짜증",
    "어이없음",
    "패배/자기혐오",
    "귀찮음",
    "힘듦/지ستان",
    "즐거움/신남",
    "깨달음",
    "죄책감",
    "증오/혐오",
    "흐뭇함(귀여움/예쁨)",
    "당황/놀람",
    "경악",
    "부담/ستان리스",
    "서러움",
    "재미없음",
    "불쌍함/연민",
    "놀람",
    "행복",
    "불안/걱정",
    "기쁨",
    "안심/ستان라움",
]

# 오타 수정된 버전 (Unicode 깨짐 방지)
KOTE_LABELS_CLEAN = [
    "불평/불만",
    "환영/호의",
    "감동/감사",
    "지긋지긋",
    "고마운",
    "슬픔",
    "화남/분노",
    "존경",
    "기대감",
    "우쭐댐/으시댐",
    "안타까움/실망",
    "비장함",
    "의심/불신",
    "뿌듯함",
    "편안/쾌적",
    "신기함/관심",
    "아껴주는",
    "부끄러움",
    "공포/무서움",
    "절망",
    "한심함",
    "역겨운/징그러운",
    "짜증",
    "어이없음",
    "패배/자기혐오",
    "귀찮음",
    "힘듦/지침",
    "즐거움/신남",
    "깨달음",
    "죄책감",
    "증오/혐오",
    "흐뭇함(귀여움/예쁨)",
    "당황/놀람",
    "경악",
    "부담/압박",
    "서러움",
    "재미없음",
    "불쌍함/연민",
    "놀람",
    "행복",
    "불안/걱정",
    "기쁨",
    "안심/안도",
]

# KcELECTRA KOTE 모델 (HuggingFace)
DEFAULT_MODEL_NAME = "searle-j/kote_for_easygoing_people"


class EmotionAnalyzer:
    """KcELECTRA + KOTE 43감정 분류기."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, device: str | None = None):
        self.model_name = model_name
        self.device_name = device
        self.model = None
        self.tokenizer = None
        self.device = None
        self.labels = KOTE_LABELS_CLEAN

    def load_model(self) -> None:
        """KcELECTRA 모델과 토크나이저를 GPU/CPU에 로드."""
        if self.model is not None:
            return
        if not TORCH_AVAILABLE:
            logger.warning("Cannot load EmotionAnalyzer — torch not installed")
            return
        logger.info("Loading EmotionAnalyzer model: %s", self.model_name)

        if self.device_name:
            self.device = torch.device(self.device_name)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()

        logger.info("EmotionAnalyzer loaded on %s", self.device)

    def _ensure_loaded(self) -> bool:
        """모델 미로드 시 자동 로드 (lazy initialization). 로드 성공 시 True."""
        if self.model is None:
            self.load_model()
        return self.model is not None

    def analyze(self, text: str, top_k: int = 5, threshold: float = 0.3) -> list[dict]:
        """감정 분석 → [{"label": "설렘", "intensity": 0.85, "confidence": 0.92}, ...]

        Multi-label 분류: sigmoid 확률이 threshold 이상인 감정을 반환.
        """
        if not self._ensure_loaded():
            return []

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            # Multi-label: sigmoid (not softmax)
            probs = torch.sigmoid(outputs.logits).squeeze(0).cpu().tolist()

        # threshold 이상인 감정만 필터링
        emotions = []
        for idx, prob in enumerate(probs):
            if prob >= threshold and idx < len(self.labels):
                emotions.append(
                    {
                        "label": self.labels[idx],
                        "intensity": round(prob, 4),
                        "confidence": round(prob, 4),
                    }
                )

        # 강도 내림차순 정렬, top_k 제한
        emotions.sort(key=lambda x: x["intensity"], reverse=True)
        return emotions[:top_k]

    def analyze_batch(self, texts: list[str], top_k: int = 5, threshold: float = 0.3) -> list[list[dict]]:
        """배치 감정 분석."""
        if not self._ensure_loaded():
            return [[] for _ in texts]

        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs_batch = torch.sigmoid(outputs.logits).cpu().tolist()

        results = []
        for probs in probs_batch:
            emotions = []
            for idx, prob in enumerate(probs):
                if prob >= threshold and idx < len(self.labels):
                    emotions.append(
                        {
                            "label": self.labels[idx],
                            "intensity": round(prob, 4),
                            "confidence": round(prob, 4),
                        }
                    )
            emotions.sort(key=lambda x: x["intensity"], reverse=True)
            results.append(emotions[:top_k])
        return results

    def get_dominant_emotion(self, text: str) -> dict | None:
        """가장 강한 감정 1개 반환."""
        emotions = self.analyze(text, top_k=1, threshold=0.1)
        return emotions[0] if emotions else None


@lru_cache(maxsize=1)
def get_emotion_analyzer() -> EmotionAnalyzer:
    """싱글턴 EmotionAnalyzer 인스턴스. 모델 로드는 첫 사용 시 lazy로 수행."""
    return EmotionAnalyzer()
