"""PromptCompiler 단위 테스트."""

from app.prompt.compiler import PromptCompiler


class TestPromptCompiler:
    def setup_method(self):
        self.compiler = PromptCompiler()

    def _make_persona(self, **overrides):
        base = {
            "persona_key": "test_char",
            "display_name": "테스트 캐릭터",
            "system_prompt": "나는 웹툰 리뷰를 도와주는 캐릭터야.",
            "style_rules": None,
            "catchphrases": None,
            "age_rating": "all",
        }
        base.update(overrides)
        return base

    def test_compile_always_starts_with_policy_layer(self):
        persona = self._make_persona()
        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=[],
            session_summary=None,
            recent_messages=[],
        )

        assert len(messages) >= 1
        assert messages[0]["role"] == "system"
        assert "PII" in messages[0]["content"]
        assert "spoiler" in messages[0]["content"].lower()

    def test_compile_includes_persona_block(self):
        persona = self._make_persona(display_name="미니")
        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=[],
            session_summary=None,
            recent_messages=[],
        )

        persona_msg = messages[1]
        assert persona_msg["role"] == "system"
        assert "미니" in persona_msg["content"]

    def test_compile_includes_style_rules(self):
        persona = self._make_persona(style_rules={"tone": "반말", "emoji": True})
        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=[],
            session_summary=None,
            recent_messages=[],
        )

        persona_msg = messages[1]["content"]
        assert "반말" in persona_msg

    def test_compile_includes_catchphrases(self):
        persona = self._make_persona(catchphrases=["그럼 뭐~", "대박!"])
        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=[],
            session_summary=None,
            recent_messages=[],
        )

        persona_msg = messages[1]["content"]
        assert "그럼 뭐~" in persona_msg

    def test_compile_includes_lorebook(self):
        persona = self._make_persona()
        lorebook = [
            {"title": "세계관", "content": "마법이 존재하는 세계", "tags": ["판타지"]},
            {"title": "주인공", "content": "용사 김철수", "tags": []},
        ]
        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=lorebook,
            session_summary=None,
            recent_messages=[],
        )

        # 로어북은 system 메시지로 포함
        lore_msg = messages[2]
        assert lore_msg["role"] == "system"
        assert "세계관" in lore_msg["content"]
        assert "마법" in lore_msg["content"]
        assert "판타지" in lore_msg["content"]

    def test_compile_skips_lorebook_when_empty(self):
        persona = self._make_persona()
        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=[],
            session_summary=None,
            recent_messages=[],
        )

        # policy + persona = 2개 system 메시지만
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 2

    def test_compile_includes_session_summary(self):
        persona = self._make_persona()
        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=[],
            session_summary="이전에 웹툰 추천을 받았음",
            recent_messages=[],
        )

        summary_found = any("이전에 웹툰 추천" in m["content"] for m in messages)
        assert summary_found

    def test_compile_includes_recent_messages(self):
        persona = self._make_persona()
        history = [
            {"role": "user", "content": "이번 화 어땠어?"},
            {"role": "assistant", "content": "감동적이었지!"},
        ]
        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=[],
            session_summary=None,
            recent_messages=history,
        )

        # 히스토리가 포함됨
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_compile_layer_order(self):
        """레이어 순서: policy → persona → lorebook → summary → history."""
        persona = self._make_persona()
        lorebook = [{"title": "설정", "content": "내용", "tags": []}]
        history = [{"role": "user", "content": "질문"}]

        messages = self.compiler.compile(
            persona=persona,
            lorebook_entries=lorebook,
            session_summary="요약 텍스트",
            recent_messages=history,
        )

        # 순서 검증
        assert messages[0]["role"] == "system"  # policy
        assert "PII" in messages[0]["content"]
        assert messages[1]["role"] == "system"  # persona
        assert messages[2]["role"] == "system"  # lorebook
        assert messages[3]["role"] == "system"  # summary
        assert messages[4]["role"] == "user"    # history
