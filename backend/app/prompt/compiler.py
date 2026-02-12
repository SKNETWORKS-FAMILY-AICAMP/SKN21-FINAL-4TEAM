class PromptCompiler:
    """프롬프트 레이어 조합기.

    레이어 순서:
    1. 불변 정책 (스포일러/연령/PII/저작권)
    2. 사용자 정의 페르소나
    3. 정책 상태
    4. 사용자 정의 로어북
    5. 세션 요약 + 최근 대화
    6. 근거 번들
    """

    async def compile(
        self,
        persona: dict,
        policy_state: dict,
        lorebook_entries: list[dict],
        session_summary: str | None,
        recent_messages: list[dict],
        evidence_bundle: dict,
    ) -> list[dict]:
        """최종 프롬프트 메시지 리스트 생성."""
        raise NotImplementedError
