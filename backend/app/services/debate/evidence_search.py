"""claim → LLM 키워드 추출 → DuckDuckGo 검색 → 출처 포함 근거 반환."""

import asyncio
import json
import logging
from dataclasses import dataclass, field

import httpx
from ddgs import DDGS

from app.core.config import settings

logger = logging.getLogger(__name__)

KEYWORD_PROMPT = """다음 주장에서 영어 웹 검색 키워드를 추출하세요.
- 핵심 개념 2~3개 (너무 많으면 안 됨)
- 반드시 영어로 변환
- JSON 배열만 출력, 설명 없이

주장: {claim}

출력 예시: ["AI regulation startup investment decline", "EU AI Act 2024 funding"]"""


@dataclass
class EvidenceResult:
    text: str
    sources: list[str] = field(default_factory=list)

    def format(self) -> str:
        """evidence 필드에 삽입할 텍스트를 반환한다."""
        sources_line = " | ".join(self.sources) if self.sources else "출처 없음"
        return f"{self.text}\n\n[출처: {sources_line}]"


class EvidenceSearchService:
    """claim에 대한 웹 근거를 검색해 출처와 함께 반환한다.

    1. LLM(gpt-4o-mini)으로 claim → 영어 키워드 추출
    2. 키워드별 DuckDuckGo 검색 (병렬)
    3. 결과 중복 제거 후 EvidenceResult 반환
    """

    async def search(self, claim: str) -> EvidenceResult | None:
        """claim에 대한 웹 근거를 검색한다. 실패 시 None을 반환한다."""
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

                return self._aggregate(results)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Evidence search timed out for claim: %.60s...", claim)
            return None
        except Exception as exc:
            logger.warning("Evidence search failed: %s", exc)
            return None

    async def search_by_query(self, query: str) -> EvidenceResult | None:
        """이미 추출된 검색 쿼리로 직접 DuckDuckGo 검색을 실행한다.

        search()와 달리 LLM 키워드 추출 단계를 스킵하여 비용·지연을 절감한다.
        tool_call.query처럼 이미 키워드가 준비된 경우 사용한다.
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
                return self._aggregate(results)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Evidence search_by_query timed out for query: %.60s...", query)
            return None
        except Exception as exc:
            logger.warning("Evidence search_by_query failed: %s", exc)
            return None

    async def _extract_keywords(self, claim: str) -> list[str]:
        """LLM으로 claim에서 영어 검색 키워드를 추출한다."""
        # TODO(next-PR): generate_byok()로 교체 — InferenceClient 컨벤션 준수 + 연결 풀 재사용
        api_key = settings.openai_api_key
        if not api_key:
            logger.debug("OpenAI API key not set — skipping keyword extraction")
            return []

        claim = claim.strip()
        if not claim or len(claim) > 2000:
            return []

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": settings.debate_evidence_keyword_model,
                        "messages": [{"role": "user", "content": KEYWORD_PROMPT.format(claim=claim)}],
                        "temperature": 0,
                        "max_tokens": 80,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    logger.debug("OpenAI returned empty choices for keyword extraction")
                    return []
                content = choices[0]["message"]["content"].strip()
                result = json.loads(content)
                return result if isinstance(result, list) else []
        except Exception:
            logger.debug("Keyword extraction failed", exc_info=True)
            return []

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
            except asyncio.TimeoutError:
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

    def _aggregate(self, results: list[dict]) -> EvidenceResult:
        """중복 URL 제거 후 snippet과 출처를 조합한다."""
        seen: set[str] = set()
        snippets: list[str] = []
        sources: list[str] = []

        for r in results:
            url = r.get("href", "")
            if not url or url in seen:
                continue
            seen.add(url)

            title = r.get("title", "")
            body = r.get("body", "")[:200]
            if body:
                snippets.append(f"- {title}: {body}")
                sources.append(url)

            if len(sources) >= 5:
                break

        return EvidenceResult(text="\n".join(snippets), sources=sources)
