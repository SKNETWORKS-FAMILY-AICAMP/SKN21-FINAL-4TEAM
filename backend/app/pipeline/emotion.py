class EmotionAnalyzer:
    """KcELECTRA + KOTE 43감정 분류기."""

    def __init__(self):
        self.model = None

    async def load_model(self):
        raise NotImplementedError

    async def analyze(self, text: str) -> list[dict]:
        """감정 분석 → [{"label": "설렘", "intensity": 0.85, "confidence": 0.92}, ...]"""
        raise NotImplementedError
