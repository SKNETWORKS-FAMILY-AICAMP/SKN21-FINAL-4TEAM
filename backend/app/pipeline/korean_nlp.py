import logging
import re
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    from kiwipiepy import Kiwi

    KIWI_AVAILABLE = True
except ImportError:
    KIWI_AVAILABLE = False
    logger.warning("kiwipiepy not installed — KoreanNLP will return basic fallback results")

# 키워드 추출 대상 품사 (체언 + 용언 어근)
_KEYWORD_POS = {"NNG", "NNP", "NNB", "VV", "VA", "XR"}


class KoreanNLP:
    """Kiwi(kiwipiepy) 기반 한국어 NLP 처리."""

    def __init__(self):
        self.kiwi: Kiwi | None = None

    def initialize(self) -> None:
        """Kiwi 한국어 형태소 분석기 초기화."""
        if self.kiwi is not None:
            return
        if not KIWI_AVAILABLE:
            logger.warning("Cannot initialize KoreanNLP — kiwipiepy not installed")
            return
        logger.info("Initializing Kiwi Korean NLP...")
        self.kiwi = Kiwi(num_workers=0)
        logger.info("Kiwi initialized.")

    def _ensure_initialized(self) -> bool:
        """미초기화 시 자동 초기화 (lazy initialization). 성공 시 True."""
        if self.kiwi is None:
            self.initialize()
        return self.kiwi is not None

    def tokenize(self, text: str) -> list[str]:
        """형태소 분석 → 토큰 리스트."""
        if not self._ensure_initialized():
            return text.split()
        result = self.kiwi.tokenize(text)
        return [token.form for token in result]

    def tokenize_with_pos(self, text: str) -> list[tuple[str, str]]:
        """형태소 분석 → (form, pos) 튜플 리스트."""
        if not self._ensure_initialized():
            return [(w, "NNG") for w in text.split()]
        result = self.kiwi.tokenize(text)
        return [(token.form, token.tag) for token in result]

    def extract_keywords(self, text: str, top_k: int = 10) -> list[str]:
        """핵심 키워드 추출 (명사/동사/형용사 기준, 빈도순)."""
        if not self._ensure_initialized():
            words = [w for w in text.split() if len(w) > 1]
            return words[:top_k]
        result = self.kiwi.tokenize(text)

        freq: dict[str, int] = {}
        for token in result:
            if token.tag in _KEYWORD_POS and len(token.form) > 1:
                freq[token.form] = freq.get(token.form, 0) + 1

        sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_keywords[:top_k]]

    def normalize(self, text: str) -> str:
        """텍스트 정규화 (띄어쓰기 교정)."""
        if not self._ensure_initialized():
            return text
        result = self.kiwi.join(self.kiwi.tokenize(text))
        return result

    def split_sentences(self, text: str) -> list[str]:
        """문장 분리."""
        if not self._ensure_initialized():
            return [s.strip() for s in re.split(r"[.!?]\s+", text) if s.strip()]
        sentences = self.kiwi.split_into_sents(text)
        return [sent.text for sent in sentences]


@lru_cache(maxsize=1)
def get_korean_nlp() -> KoreanNLP:
    """싱글턴 KoreanNLP 인스턴스. 초기화는 첫 사용 시 lazy로 수행."""
    return KoreanNLP()
