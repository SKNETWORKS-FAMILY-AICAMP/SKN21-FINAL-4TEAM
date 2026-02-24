import logging
import re
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False
    logger.warning("presidio not installed — PIIDetector will use regex-only fallback")

# 한국어 PII 정규식 (Presidio 없을 때 fallback용 + Presidio 패턴 등록용)
_KR_PHONE_REGEX = r"01[0-9]-?\d{3,4}-?\d{4}"
_KR_RESIDENT_ID_REGEX = r"\d{6}-?[1-4]\d{6}"
_KR_EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
_KR_CARD_REGEX = r"\d{4}-?\d{4}-?\d{4}-?\d{4}"
_KR_ACCOUNT_REGEX = r"\d{3,4}-\d{2,6}-\d{4,6}"

# Presidio 사용 시에만 Pattern 객체 생성
if PRESIDIO_AVAILABLE:
    _KR_PHONE_PATTERN = Pattern(name="kr_phone", regex=_KR_PHONE_REGEX, score=0.85)
    _KR_RESIDENT_ID_PATTERN = Pattern(name="kr_resident_id", regex=_KR_RESIDENT_ID_REGEX, score=0.95)
    _KR_EMAIL_PATTERN = Pattern(name="kr_email", regex=_KR_EMAIL_REGEX, score=0.85)
    _KR_CARD_PATTERN = Pattern(name="kr_card", regex=_KR_CARD_REGEX, score=0.80)
    _KR_ACCOUNT_PATTERN = Pattern(name="kr_account", regex=_KR_ACCOUNT_REGEX, score=0.60)

# Fallback 마스킹 패턴 (presidio 미설치 시 사용)
_FALLBACK_PATTERNS = [
    (_KR_RESIDENT_ID_REGEX, "<주민번호>"),
    (_KR_PHONE_REGEX, "<전화번호>"),
    (_KR_EMAIL_REGEX, "<이메일>"),
    (_KR_CARD_REGEX, "<카드번호>"),
    (_KR_ACCOUNT_REGEX, "<계좌번호>"),
]


class PIIDetector:
    """Presidio 기반 PII 탐지/마스킹. 한국어+영어 지원. Presidio 미설치 시 regex fallback."""

    def __init__(self):
        self.analyzer = None
        self.anonymizer = None
        self._initialized = False

    def initialize(self) -> None:
        """Presidio 분석기/익명화기 초기화 + 한국어 패턴 등록."""
        if self._initialized:
            return
        if not PRESIDIO_AVAILABLE:
            logger.warning("PIIDetector using regex-only fallback — presidio not installed")
            self._initialized = True
            return

        logger.info("Initializing PII Detector...")
        try:
            self.analyzer = AnalyzerEngine()

            # 한국어 패턴 인식기 — "en" 언어로 등록 (Presidio 기본 NLP 엔진이 en만 지원)
            kr_phone_recognizer = PatternRecognizer(
                supported_entity="KR_PHONE_NUMBER",
                patterns=[_KR_PHONE_PATTERN],
                supported_language="en",
            )
            kr_resident_recognizer = PatternRecognizer(
                supported_entity="KR_RESIDENT_ID",
                patterns=[_KR_RESIDENT_ID_PATTERN],
                supported_language="en",
            )
            kr_email_recognizer = PatternRecognizer(
                supported_entity="EMAIL_ADDRESS",
                patterns=[_KR_EMAIL_PATTERN],
                supported_language="en",
            )
            kr_card_recognizer = PatternRecognizer(
                supported_entity="KR_CREDIT_CARD",
                patterns=[_KR_CARD_PATTERN],
                supported_language="en",
            )
            kr_account_recognizer = PatternRecognizer(
                supported_entity="KR_BANK_ACCOUNT",
                patterns=[_KR_ACCOUNT_PATTERN],
                supported_language="en",
            )

            self.analyzer.registry.add_recognizer(kr_phone_recognizer)
            self.analyzer.registry.add_recognizer(kr_resident_recognizer)
            self.analyzer.registry.add_recognizer(kr_email_recognizer)
            self.analyzer.registry.add_recognizer(kr_card_recognizer)
            self.analyzer.registry.add_recognizer(kr_account_recognizer)

            self.anonymizer = AnonymizerEngine()
            logger.info("PII Detector initialized.")
        except BaseException as e:
            # spaCy 모델 다운로드 실패 시 SystemExit(1) 발생 → BaseException으로 잡아야 함
            logger.warning("PII Detector init failed — fallback to regex-only: %s", e)
            self.analyzer = None
            self.anonymizer = None
        self._initialized = True

    def _ensure_initialized(self) -> None:
        """미초기화 시 자동 초기화 (lazy initialization)."""
        if not self._initialized:
            self.initialize()

    def detect(self, text: str, language: str = "en") -> list[dict]:
        """PII 탐지 결과 반환 (마스킹 없이)."""
        self._ensure_initialized()

        if self.analyzer is not None:
            results: list[RecognizerResult] = self.analyzer.analyze(text=text, language="en")
            results = self._deduplicate(results)
            return [
                {
                    "entity_type": r.entity_type,
                    "start": r.start,
                    "end": r.end,
                    "score": r.score,
                    "text": text[r.start : r.end],
                }
                for r in results
            ]

        # Fallback: regex 기반 탐지
        detections = []
        for pattern, label in _FALLBACK_PATTERNS:
            for m in re.finditer(pattern, text):
                detections.append(
                    {
                        "entity_type": label.strip("<>"),
                        "start": m.start(),
                        "end": m.end(),
                        "score": 0.8,
                        "text": m.group(),
                    }
                )
        return detections

    def mask(self, text: str, language: str = "en") -> str:
        """PII 탐지 후 마스킹 처리된 텍스트 반환."""
        self._ensure_initialized()

        if self.analyzer is not None and self.anonymizer is not None:
            results: list[RecognizerResult] = self.analyzer.analyze(text=text, language="en")
            if not results:
                return text
            operators = {
                "DEFAULT": OperatorConfig("replace", {"new_value": "<PII>"}),
                "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<전화번호>"}),
                "KR_PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<전화번호>"}),
                "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<이메일>"}),
                "PERSON": OperatorConfig("replace", {"new_value": "<이름>"}),
                "CREDIT_CARD": OperatorConfig("replace", {"new_value": "<카드번호>"}),
                "KR_CREDIT_CARD": OperatorConfig("replace", {"new_value": "<카드번호>"}),
                "KR_RESIDENT_ID": OperatorConfig("replace", {"new_value": "<주민번호>"}),
                "KR_BANK_ACCOUNT": OperatorConfig("replace", {"new_value": "<계좌번호>"}),
            }
            anonymized = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=operators,
            )
            return anonymized.text

        # Fallback: regex 기반 마스킹
        masked = text
        for pattern, replacement in _FALLBACK_PATTERNS:
            masked = re.sub(pattern, replacement, masked)
        return masked

    def has_pii(self, text: str, language: str = "en", threshold: float = 0.5) -> bool:
        """PII 포함 여부 (빠른 체크)."""
        detections = self.detect(text, language)
        return any(d["score"] >= threshold for d in detections)

    @staticmethod
    def _deduplicate(results: list) -> list:
        """겹치는 범위의 결과에서 높은 점수만 유지."""
        if not results:
            return []
        sorted_results = sorted(results, key=lambda r: (r.start, -r.score))
        deduped = [sorted_results[0]]
        for r in sorted_results[1:]:
            prev = deduped[-1]
            if r.start < prev.end:
                if r.score > prev.score:
                    deduped[-1] = r
            else:
                deduped.append(r)
        return deduped


@lru_cache(maxsize=1)
def get_pii_detector() -> PIIDetector:
    """싱글턴 PIIDetector 인스턴스. 초기화는 첫 사용 시 lazy로 수행."""
    return PIIDetector()
