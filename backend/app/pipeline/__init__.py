"""NLP/ML 파이프라인 모듈.

pipeline_lazy_load=True (기본값): 각 파이프라인이 첫 호출 시 모델을 로드.
pipeline_lazy_load=False: 앱 startup 시 모든 모델을 한 번에 로드.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def preload_pipelines() -> None:
    """앱 시작 시 모든 파이프라인 모델을 미리 로드 (pipeline_lazy_load=False일 때)."""
    logger.info("Preloading pipeline models...")

    from app.pipeline.korean_nlp import get_korean_nlp

    get_korean_nlp()
    logger.info("KoreanNLP loaded.")

    from app.pipeline.pii import get_pii_detector

    get_pii_detector()
    logger.info("PIIDetector loaded.")

    device = settings.pipeline_device or None

    from app.pipeline.emotion import EmotionAnalyzer

    analyzer = EmotionAnalyzer(model_name=settings.emotion_model, device=device)
    analyzer.load_model()
    logger.info("EmotionAnalyzer loaded.")

    from app.pipeline.embedding import EmbeddingService

    embedding = EmbeddingService(model_name=settings.embedding_model, device=device)
    embedding.load_model()
    logger.info("EmbeddingService loaded.")

    from app.pipeline.reranker import Reranker

    reranker = Reranker(model_name=settings.reranker_model, device=device)
    reranker.load_model()
    logger.info("Reranker loaded.")

    logger.info("All pipeline models loaded.")
