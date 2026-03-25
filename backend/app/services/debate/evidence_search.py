"""claim → LLM 키워드 추출 → DuckDuckGo 검색 → LLM 합성 → 출처 포함 근거 반환."""

import asyncio
import json
import logging
from dataclasses import dataclass, field

from ddgs import DDGS

from app.core.config import settings

logger = logging.getLogger(__name__)

KEYWORD_PROMPT = """다음 주장에서 웹 검색 키워드를 추출하세요.
- 영어 키워드 2~3개 + 한국어 키워드 1~2개를 함께 추출
- JSON 배열만 출력, 설명 없이

주장: {claim}

출력 예시: ["AI regulation 2024", "EU AI Act funding", "AI 규제 스타트업 투자"]"""

SYNTHESIS_PROMPT = """다음 주장과 검색된 웹 결과를 바탕으로, 주장과 직접 관련된 핵심 근거를 한국어 2~3문장으로 요약하세요.
- 주장의 내용을 뒷받침하거나 반박하는 구체적 사실·수치·사례 위주로 작성
- 원문 snippet을 그대로 나열하지 말고 주장과의 연관성을 중심으로 합성
- 출처 URL은 포함하지 마세요 (별도 처리됨)
- 검색 결과가 주제와 관련이 없으면 "검색 결과가 주제와 관련이 없습니다."라고만 반환하세요

주장:
{claim}

검색 결과:
{snippets}

요약:"""


@dataclass
class EvidenceResult:
    text: str
    sources: list[str] = field(default_factory=list)

    def format(self) -> str:
        """evidence 필드에 삽입할 텍스트를 반환한다."""
        sources_line = " | ".join(self.sources) if self.sources else "출처 없음"
        return f"{self.text}\n\n[출처: {sources_line}]"


class EvidenceSearchService:
    """claim에 대한 웹 근거를 검색해 LLM으로 합성 후 출처와 함께 반환한다.

    1. LLM(gpt-4o-mini)으로 claim → 영어 키워드 추출
    2. 키워드별 DuckDuckGo 검색 (병렬)
    3. 결과를 LLM으로 합성 → claim 연관 한국어 요약
    4. 합성 실패 시 원본 snippet concat으로 fallback
    """

    def __init__(self) -> None:
        # InferenceClient는 첫 LLM 호출 시 lazy init — import 순환 방지
        self._client: "InferenceClient | None" = None
        self._owns_client = False

    def _get_client(self) -> "InferenceClient":
        """InferenceClient를 lazy init으로 반환한다."""
        if self._client is None:
            from app.services.llm.inference_client import InferenceClient

            self._client = InferenceClient()
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        """소유한 InferenceClient를 닫는다."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
            self._owns_client = False

    async def search(self, claim: str, exclude_urls: set[str] | None = None) -> "EvidenceResult | None":
        """claim에 대한 웹 근거를 검색·합성한다. 실패 시 None을 반환한다.

        Args:
            claim: 검색 대상 주장 텍스트.
            exclude_urls: 이미 이전 턴에서 사용된 출처 URL 집합. 동일 출처 반복 방지용.
        """
        if not settings.debate_evidence_search_enabled:
            return None

        try:
            async with asyncio.timeout(settings.debate_evidence_search_timeout):
                keywords = await self._extract_keywords(claim)
                if not keywords:
                    return None

                results = await self._search_all(keywords)
                if not results:
                    return None

                aggregated = self._aggregate(results, exclude_urls=exclude_urls)
                return await self._synthesize_or_fallback(claim, aggregated)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Evidence search timed out for claim: %.60s...", claim)
            return None
        except Exception as exc:
            logger.warning("Evidence search failed: %s", exc)
            return None

    async def search_by_query(
        self,
        query: str,
        claim: str | None = None,
        exclude_urls: set[str] | None = None,
    ) -> "EvidenceResult | None":
        """이미 추출된 검색 쿼리로 DuckDuckGo 검색 후 한국어로 합성해 반환한다.

        tool_call.query처럼 키워드가 이미 준비된 경우 사용한다.
        claim을 전달하면 search()와 동일하게 LLM 합성 단계를 거쳐 한국어 요약을 반환한다.
        claim 없이 합성 실패 시에는 raw snippet으로 fallback한다.

        Args:
            query: 검색 쿼리 문자열.
            claim: 합성 시 맥락으로 사용할 주장 텍스트. 없으면 query를 대신 사용한다.
            exclude_urls: 이미 이전 턴에서 사용된 출처 URL 집합. 동일 출처 반복 방지용.
        """
        if not settings.debate_evidence_search_enabled:
            return None
        if not query or not query.strip():
            return None

        try:
            async with asyncio.timeout(settings.debate_evidence_search_timeout):
                results = await self._search_all([query.strip()])
                if not results:
                    return None
                aggregated = self._aggregate(results, exclude_urls=exclude_urls)
                # claim이 없으면 query를 합성 맥락으로 사용 — raw snippet 그대로 반환 방지
                return await self._synthesize_or_fallback(claim or query, aggregated)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Evidence search_by_query timed out for query: %.60s...", query)
            return None
        except Exception as exc:
            logger.warning("Evidence search_by_query failed: %s", exc)
            return None

    async def _extract_keywords(self, claim: str) -> list[str]:
        """InferenceClient로 claim에서 영어 검색 키워드를 추출한다."""
        api_key = settings.openai_api_key
        if not api_key:
            logger.debug("OpenAI API key not set — skipping keyword extraction")
            return []

        claim = claim.strip()
        if not claim or len(claim) > 2000:
            return []

        try:
            client = self._get_client()
            result = await asyncio.wait_for(
                client.generate_byok(
                    provider="openai",
                    model_id=settings.debate_evidence_keyword_model,
                    api_key=api_key,
                    messages=[{"role": "user", "content": KEYWORD_PROMPT.format(claim=claim)}],
                    max_tokens=80,
                    temperature=0,
                ),
                timeout=8.0,
            )
            content = result.get("content", "").strip()
            if not content:
                return []
            parsed = json.loads(content)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            logger.debug("Keyword extraction failed", exc_info=True)
            return []

    async def _synthesize(self, claim: str, snippets_text: str, api_key: str) -> str:
        """DuckDuckGo snippet을 claim과 연관된 한국어 요약으로 합성한다.

        Args:
            claim: 근거를 찾고 있는 주장 텍스트.
            snippets_text: _aggregate()가 반환한 snippet 연결 텍스트.
            api_key: OpenAI API 키.

        Returns:
            합성된 한국어 요약 문자열.

        Raises:
            Exception: LLM 호출 실패 또는 타임아웃 시 — 호출자가 fallback 처리.
        """
        client = self._get_client()
        prompt = SYNTHESIS_PROMPT.format(claim=claim[:800], snippets=snippets_text[:1500])
        result = await asyncio.wait_for(
            client.generate_byok(
                provider="openai",
                model_id=settings.debate_evidence_synthesis_model,
                api_key=api_key,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.debate_evidence_synthesis_max_tokens,
                temperature=0.3,
            ),
            timeout=5.0,
        )
        synthesized = result.get("content", "").strip()
        if not synthesized:
            raise ValueError("LLM returned empty synthesis")
        return synthesized

    async def _synthesize_or_fallback(self, claim: str, aggregated: "EvidenceResult") -> "EvidenceResult":
        """합성 시도 후 실패 시 원본 aggregate 결과로 fallback한다."""
        api_key = settings.openai_api_key
        if not api_key or not aggregated.text:
            return aggregated

        try:
            synthesized_text = await self._synthesize(claim, aggregated.text, api_key)
            return EvidenceResult(text=synthesized_text, sources=aggregated.sources)
        except Exception as exc:
            logger.debug("Evidence synthesis failed, using raw snippets: %s", exc)
            return aggregated

    async def _search_all(self, keywords: list[str]) -> list[dict]:
        """키워드별 DuckDuckGo 검색을 병렬 실행한다.

        반환값: 중복 URL이 제거된 검색 결과 dict 목록.
        키워드는 최대 10개로 상한하며, 키워드당 5초 타임아웃을 적용한다.
        """
        loop = asyncio.get_running_loop()
        capped = [kw.strip() for kw in keywords if kw.strip()][:10]

        async def _run_with_timeout(kw: str) -> list[dict]:
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(None, self._ddg_search, kw),
                    timeout=5.0,
                )
            except TimeoutError:
                logger.warning("DDG search timed out: %s", kw)
                return []
            except asyncio.CancelledError:
                raise  # 취소 신호 재전파
            except Exception as exc:
                logger.warning("DDG search error (kw=%s): %s", kw, exc)
                return []

        nested = await asyncio.gather(*[_run_with_timeout(kw) for kw in capped])

        seen_urls: set[str] = set()
        flat: list[dict] = []
        for result in nested:
            for item in result:
                url = item.get("href", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    flat.append(item)
        return flat

    def _ddg_search(self, query: str) -> list[dict]:
        """DuckDuckGo 텍스트 검색 (동기). run_in_executor로 호출된다.
        빈 쿼리이면 빈 리스트를 반환한다."""
        if not query.strip():
            return []
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=settings.debate_evidence_search_max_results))
        except Exception as exc:
            logger.debug("DDG '%s' failed: %s", query, exc)
            return []

    def _aggregate(self, results: list[dict], exclude_urls: set[str] | None = None) -> "EvidenceResult":
        """중복 URL 제거 후 snippet과 출처를 조합한다.

        Args:
            results: DuckDuckGo 검색 결과 목록.
            exclude_urls: 이미 이전 턴에서 사용된 출처 URL — 크로스-턴 중복 방지.
        """
        # exclude_urls 포함 초기화 — 이전 턴 출처가 다시 등장해도 건너뜀
        seen: set[str] = set(exclude_urls) if exclude_urls else set()
        snippets: list[str] = []
        sources: list[str] = []

        for r in results:
            url = r.get("href", "")
            if not url or url in seen:
                continue
            seen.add(url)

            title = r.get("title", "")
            body = r.get("body", "")[:400]
            if body:
                snippets.append(f"- {title}: {body}")
                sources.append(url)

            if len(sources) >= 5:
                break

        return EvidenceResult(text="\n".join(snippets), sources=sources)
