"""PIIDetector 파이프라인 단위 테스트."""

from app.pipeline.pii import PIIDetector


class TestPIIDetector:
    def setup_method(self):
        self.detector = PIIDetector()
        self.detector.initialize()

    def test_initialize_creates_engines(self):
        assert self.detector.analyzer is not None
        assert self.detector.anonymizer is not None

    def test_double_initialize_is_idempotent(self):
        ref = self.detector.analyzer
        self.detector.initialize()
        assert self.detector.analyzer is ref

    # ── 한국어 전화번호 ──

    def test_detect_korean_phone_number(self):
        text = "제 번호는 010-1234-5678이에요"
        results = self.detector.detect(text)
        assert len(results) > 0
        entity_types = {r["entity_type"] for r in results}
        assert "KR_PHONE_NUMBER" in entity_types or "PHONE_NUMBER" in entity_types

    def test_mask_korean_phone_number(self):
        text = "제 번호는 010-1234-5678이에요"
        masked = self.detector.mask(text)
        assert "010-1234-5678" not in masked
        assert "<전화번호>" in masked or "<PII>" in masked

    # ── 이메일 ──

    def test_detect_email(self):
        text = "이메일은 user@example.com 입니다"
        results = self.detector.detect(text)
        entity_types = {r["entity_type"] for r in results}
        assert "EMAIL_ADDRESS" in entity_types

    def test_mask_email(self):
        text = "연락처: test@gmail.com"
        masked = self.detector.mask(text)
        assert "test@gmail.com" not in masked

    # ── 주민등록번호 ──

    def test_detect_korean_resident_id(self):
        text = "주민번호 901231-1234567 확인해주세요"
        results = self.detector.detect(text)
        assert len(results) > 0

    def test_mask_korean_resident_id(self):
        text = "주민번호 901231-1234567"
        masked = self.detector.mask(text)
        assert "901231-1234567" not in masked

    # ── PII 없는 텍스트 ──

    def test_detect_no_pii_returns_empty(self):
        text = "오늘 웹툰 재미있었어요"
        results = self.detector.detect(text)
        assert len(results) == 0

    def test_mask_no_pii_returns_original(self):
        text = "이번 에피소드 감동적이었어요"
        masked = self.detector.mask(text)
        assert masked == text

    # ── has_pii ──

    def test_has_pii_true(self):
        assert self.detector.has_pii("전화번호 010-9999-8888")

    def test_has_pii_false(self):
        assert not self.detector.has_pii("웹툰 리뷰입니다")

    # ── 복합 PII ──

    def test_mask_multiple_pii(self):
        text = "이름 홍길동, 번호 010-1111-2222, 메일 hong@test.com"
        masked = self.detector.mask(text)
        assert "010-1111-2222" not in masked
        assert "hong@test.com" not in masked

    # ── 중복 제거 ──

    def test_deduplicate_overlapping_results(self):
        from presidio_analyzer import RecognizerResult
        results = [
            RecognizerResult("PHONE", 0, 13, 0.8),
            RecognizerResult("KR_PHONE", 0, 13, 0.9),
        ]
        deduped = PIIDetector._deduplicate(results)
        assert len(deduped) == 1
        assert deduped[0].score == 0.9
