import json


class PromptCompiler:
    """프롬프트 레이어 조합기.

    레이어 순서:
    1. 불변 정책 (스포일러/연령/PII/저작권)
    1.5. 세계관 이벤트 (大前提)
    2. 사용자 정의 페르소나 (scenario 포함)
    2.3. 관계 상태 (호감도/단계)
    2.5. 사용자 페르소나 ([User Character])
    2.7. 예시 대화 (few-shot)
    3. 로어북
    3.5. 사용자 기억 ([User Memories])
    4. 세션 요약
    5. 최근 대화 히스토리
    """

    POLICY_LAYER = (
        "Follow these rules strictly:\n"
        "- Never reveal real personal information (PII) about users.\n"
        "- Respect spoiler settings: only discuss episodes the user has read.\n"
        "- Follow age rating restrictions for this persona.\n"
        "- Do not reproduce copyrighted content verbatim."
    )

    def compile(
        self,
        persona: dict,
        lorebook_entries: list[dict],
        session_summary: str | None,
        recent_messages: list[dict],
        user_persona: dict | None = None,
        relationship: dict | None = None,
        user_memories: list[dict] | None = None,
        world_events: list[dict] | None = None,
    ) -> list[dict]:
        """최종 프롬프트 메시지 리스트 생성."""
        messages = []

        # Layer 1: 불변 정책
        messages.append({"role": "system", "content": self.POLICY_LAYER})

        # Layer 1.5: 세계관 이벤트 (大前提)
        if world_events:
            world_text = self._build_world_events_block(world_events)
            messages.append({"role": "system", "content": world_text})

        # Layer 2: 페르소나 (scenario 포함)
        persona_text = self._build_persona_block(persona)
        messages.append({"role": "system", "content": persona_text})

        # Layer 2.3: 관계 상태
        if relationship:
            rel_text = self._build_relationship_block(relationship)
            messages.append({"role": "system", "content": rel_text})

        # Layer 2.5: 사용자 페르소나
        if user_persona:
            up_text = self._build_user_persona_block(user_persona)
            messages.append({"role": "system", "content": up_text})

        # Layer 2.7: 예시 대화 (few-shot)
        if persona.get("example_dialogues"):
            example_text = self._build_example_dialogues(persona["example_dialogues"], persona["display_name"])
            messages.append({"role": "system", "content": example_text})

        # Layer 3: 로어북
        if lorebook_entries:
            lore_text = self._build_lorebook_block(lorebook_entries)
            messages.append({"role": "system", "content": lore_text})

        # Layer 3.5: 사용자 기억
        if user_memories:
            mem_text = self._build_memories_block(user_memories)
            messages.append({"role": "system", "content": mem_text})

        # Layer 4: 세션 요약
        if session_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"[Session Summary]\n{session_summary}",
                }
            )

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
        if persona.get("scenario"):
            parts.append(f"\n[Scenario]\n{persona['scenario']}")
        if persona.get("style_rules"):
            parts.append(f"Style: {json.dumps(persona['style_rules'], ensure_ascii=False)}")
        if persona.get("catchphrases"):
            parts.append(f"Catchphrases: {', '.join(persona['catchphrases'])}")
        return "\n".join(parts)

    @staticmethod
    def _build_relationship_block(relationship: dict) -> str:
        stage_labels = {
            "stranger": "낯선 사이",
            "acquaintance": "아는 사이",
            "friend": "친구",
            "close_friend": "절친",
            "crush": "썸",
            "lover": "연인",
            "soulmate": "소울메이트",
        }
        stage = relationship.get("stage", "stranger")
        label = stage_labels.get(stage, stage)
        level = relationship.get("level", 0)
        return (
            f"[Relationship with User]\n"
            f"Stage: {label} ({stage}), Affection: {level}/1000\n"
            f"Adjust your tone, intimacy, and behavior accordingly."
        )

    @staticmethod
    def _build_user_persona_block(user_persona: dict) -> str:
        parts = [f"[User Character: {user_persona['display_name']}]"]
        if user_persona.get("description"):
            parts.append(user_persona["description"])
        return "\n".join(parts)

    @staticmethod
    def _build_example_dialogues(dialogues: list[dict], char_name: str) -> str:
        parts = ["[Example Dialogues]"]
        for d in dialogues:
            parts.append("<START>")
            if d.get("user"):
                parts.append(f"User: {d['user']}")
            if d.get("assistant"):
                parts.append(f"{char_name}: {d['assistant']}")
        return "\n".join(parts)

    @staticmethod
    def _build_lorebook_block(entries: list[dict]) -> str:
        parts = ["[Lorebook Knowledge]"]
        for entry in entries:
            tags_str = f" [{', '.join(entry['tags'])}]" if entry.get("tags") else ""
            parts.append(f"- {entry['title']}{tags_str}: {entry['content']}")
        return "\n".join(parts)

    @staticmethod
    def _build_memories_block(memories: list[dict]) -> str:
        parts = ["[User Memories - Remember these facts about the user]"]
        for m in memories:
            parts.append(f"- {m['key']}: {m['value']}")
        return "\n".join(parts)

    @staticmethod
    def _build_world_events_block(events: list[dict]) -> str:
        parts = ["[World State — 大前提: 현재 세계 상황]"]
        for e in events:
            event_type = e.get("event_type", "world_state")
            title = e.get("title", "")
            content = e.get("content", "")
            parts.append(f"- [{event_type}] {title}: {content}")
        return "\n".join(parts)
