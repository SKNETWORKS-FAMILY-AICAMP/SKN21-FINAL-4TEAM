class PIIDetector:
    """Presidio 기반 PII 탐지/마스킹."""

    def __init__(self):
        self.analyzer = None
        self.anonymizer = None

    async def initialize(self):
        raise NotImplementedError

    async def mask(self, text: str) -> str:
        """PII 탐지 후 마스킹 처리된 텍스트 반환."""
        raise NotImplementedError

    async def detect(self, text: str) -> list[dict]:
        """PII 탐지 결과 반환 (마스킹 없이)."""
        raise NotImplementedError
