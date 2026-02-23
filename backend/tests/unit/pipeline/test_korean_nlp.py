"""KoreanNLP 파이프라인 단위 테스트."""

from app.pipeline.korean_nlp import KoreanNLP


class TestKoreanNLP:
    def setup_method(self):
        self.nlp = KoreanNLP()
        self.nlp.initialize()

    def test_initialize_creates_kiwi_instance(self):
        assert self.nlp.kiwi is not None

    def test_double_initialize_is_idempotent(self):
        kiwi_ref = self.nlp.kiwi
        self.nlp.initialize()
        assert self.nlp.kiwi is kiwi_ref

    def test_tokenize_returns_list_of_strings(self):
        tokens = self.nlp.tokenize("오늘 날씨가 좋습니다")
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert all(isinstance(t, str) for t in tokens)

    def test_tokenize_with_pos_returns_tuples(self):
        result = self.nlp.tokenize_with_pos("웹툰을 봤어요")
        assert isinstance(result, list)
        assert len(result) > 0
        for form, pos in result:
            assert isinstance(form, str)
            assert isinstance(pos, str)

    def test_extract_keywords_returns_nouns_verbs(self):
        text = "이번 에피소드에서 주인공이 감동적인 대사를 하며 눈물을 흘렸다"
        keywords = self.nlp.extract_keywords(text, top_k=5)
        assert isinstance(keywords, list)
        assert len(keywords) <= 5
        # 단일 문자 키워드는 필터링됨
        assert all(len(k) > 1 for k in keywords)

    def test_extract_keywords_top_k_limit(self):
        text = "감동 슬픔 기쁨 분노 설렘 환희 공포 사랑 행복 즐거움 두려움 그리움"
        keywords = self.nlp.extract_keywords(text, top_k=3)
        assert len(keywords) <= 3

    def test_extract_keywords_empty_text(self):
        keywords = self.nlp.extract_keywords("")
        assert keywords == []

    def test_normalize_returns_string(self):
        result = self.nlp.normalize("오늘날씨가좋습니다")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_split_sentences(self):
        text = "첫 번째 문장입니다. 두 번째 문장이에요. 세 번째 문장!"
        sentences = self.nlp.split_sentences(text)
        assert isinstance(sentences, list)
        assert len(sentences) >= 2

    def test_split_sentences_single(self):
        sentences = self.nlp.split_sentences("하나의 문장만 있습니다")
        assert len(sentences) == 1
