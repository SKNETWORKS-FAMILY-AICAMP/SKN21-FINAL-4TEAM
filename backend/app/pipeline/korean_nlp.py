class KoreanNLP:
    """Kiwi(kiwipiepy) 기반 한국어 NLP 처리."""

    def __init__(self):
        self.kiwi = None

    def initialize(self):
        raise NotImplementedError

    def tokenize(self, text: str) -> list[str]:
        raise NotImplementedError

    def extract_keywords(self, text: str, top_k: int = 10) -> list[str]:
        raise NotImplementedError

    def normalize(self, text: str) -> str:
        """텍스트 정규화 (오탈자 보정, 띄어쓰기 교정)."""
        raise NotImplementedError
