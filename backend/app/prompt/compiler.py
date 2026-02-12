import json


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

    POLICY_LAYER = (
        "You are a webtoon review chatbot. Follow these rules strictly:\n"
        "- Never reveal real personal information (PII) about users.\n"
        "- Respect spoiler settings: only discuss episodes the user has read.\n"
        "- Follow age rating restrictions for this persona.\n"
        "- Do not reproduce copyrighted webtoon content verbatim."
    )

    def compile(
        self,
        persona: dict,
        lorebook_entries: list[dict],
        session_summary: str | None,
        recent_messages: list[dict],
    ) -> list[dict]:
        """최종 프롬프트 메시지 리스트 생성."""
        messages = []

        # Layer 1: 불변 정책
        messages.append({"role": "system", "content": self.POLICY_LAYER})

        # Layer 2: 페르소나
        persona_text = self._build_persona_block(persona)
        messages.append({"role": "system", "content": persona_text})

        # Layer 3: 로어북
        if lorebook_entries:
            lore_text = self._build_lorebook_block(lorebook_entries)
            messages.append({"role": "system", "content": lore_text})

        # Layer 4: 세션 요약
        if session_summary:
            messages.append({
                "role": "system",
                "content": f"[Session Summary]\n{session_summary}",
            })

        # Layer 5: 최근 대화 히스토리
        for msg in recent_messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        return messages

    @staticmethod
    def _build_persona_block(persona: dict) -> str:
        parts = [
            f"[Persona: {persona['display_name']}]",
            persona["system_prompt"],
        ]
        if persona.get("style_rules"):
            parts.append(f"Style: {json.dumps(persona['style_rules'], ensure_ascii=False)}")
        if persona.get("catchphrases"):
            parts.append(f"Catchphrases: {', '.join(persona['catchphrases'])}")
        return "\n".join(parts)

    @staticmethod
    def _build_lorebook_block(entries: list[dict]) -> str:
        parts = ["[Lorebook Knowledge]"]
        for entry in entries:
            tags_str = f" [{', '.join(entry['tags'])}]" if entry.get("tags") else ""
            parts.append(f"- {entry['title']}{tags_str}: {entry['content']}")
        return "\n".join(parts)
