#!/usr/bin/env python3
"""
시드 데이터 자동 생성 스크립트 (Idempotent).

Usage:
    cd backend
    .venv/Scripts/python.exe ../scripts/seed_data.py [--env-file .env.test]
"""
import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

# backend/ 패키지 경로 주입 (scripts/에서 실행 시)
_backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(_backend_dir))


def _load_env_file(path: str) -> None:
    """지정된 .env 파일의 환경변수를 os.environ에 로드."""
    env_path = Path(path)
    if not env_path.is_absolute():
        # CWD 기준 탐색 후 backend/ 기준 탐색
        candidates = [Path.cwd() / path, _backend_dir / path]
        env_path = next((p for p in candidates if p.exists()), env_path)

    if not env_path.exists():
        print(f"[WARN] env file not found: {path}")
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
    print(f"[INFO] Loaded env: {env_path}")


# --- 고정 UUID (idempotency 보장) ---
SEED_IDS = {
    "superadmin": uuid.UUID("00000001-0000-0000-0000-000000000001"),
    "admin": uuid.UUID("00000001-0000-0000-0000-000000000002"),
    "user1": uuid.UUID("00000001-0000-0000-0000-000000000003"),
    "user2": uuid.UUID("00000001-0000-0000-0000-000000000004"),
    "user3": uuid.UUID("00000001-0000-0000-0000-000000000005"),
    "llm_gpt4o": uuid.UUID("00000002-0000-0000-0000-000000000001"),
    "llm_gpt4o_mini": uuid.UUID("00000002-0000-0000-0000-000000000002"),
    "llm_claude": uuid.UUID("00000002-0000-0000-0000-000000000003"),
    "llm_gemini": uuid.UUID("00000002-0000-0000-0000-000000000004"),
    "plan_free": uuid.UUID("00000003-0000-0000-0000-000000000001"),
    "plan_premium": uuid.UUID("00000003-0000-0000-0000-000000000002"),
    "persona_all": uuid.UUID("00000004-0000-0000-0000-000000000001"),
    "persona_15": uuid.UUID("00000004-0000-0000-0000-000000000002"),
    "persona_18": uuid.UUID("00000004-0000-0000-0000-000000000003"),
    "board_general": uuid.UUID("00000005-0000-0000-0000-000000000001"),
    "board_review": uuid.UUID("00000005-0000-0000-0000-000000000002"),
    "board_adult": uuid.UUID("00000005-0000-0000-0000-000000000003"),
    "topic_1": uuid.UUID("00000006-0000-0000-0000-000000000001"),
    "topic_2": uuid.UUID("00000006-0000-0000-0000-000000000002"),
    "topic_3": uuid.UUID("00000006-0000-0000-0000-000000000003"),
    "template_aggressive": uuid.UUID("00000007-0000-0000-0000-000000000001"),
    "template_balanced": uuid.UUID("00000007-0000-0000-0000-000000000002"),
    "agent_1": uuid.UUID("00000008-0000-0000-0000-000000000001"),
    "agent_2": uuid.UUID("00000008-0000-0000-0000-000000000002"),
    "world_event_1": uuid.UUID("00000009-0000-0000-0000-000000000001"),
}


async def _natural_key_exists(session, model, **kwargs) -> bool:
    """natural key로 레코드 존재 여부 확인 (idempotency 보조)."""
    from sqlalchemy import select

    conditions = [getattr(model, k) == v for k, v in kwargs.items()]
    result = await session.execute(select(model).where(*conditions))
    return result.scalar_one_or_none() is not None


async def _get_user_id_by_login(session, login_id: str):
    """login_id로 실제 DB의 user UUID를 조회 (FK 참조용)."""
    from sqlalchemy import select, text

    result = await session.execute(text("SELECT id FROM users WHERE login_id = :lid"), {"lid": login_id})
    row = result.fetchone()
    return row[0] if row else None


async def seed(db_url: str) -> None:
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.auth import get_password_hash

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        print("[INFO] Seeding database...")

        # ── Users ──
        await _seed_users(session, get_password_hash)

        # 실제 DB UUID 조회 (기존 데이터와의 FK 호환)
        real_admin_id = await _get_user_id_by_login(session, "admin") or SEED_IDS["superadmin"]
        real_user1_id = await _get_user_id_by_login(session, "user1") or SEED_IDS["user1"]
        real_user2_id = await _get_user_id_by_login(session, "user2") or SEED_IDS["user2"]

        # ── LLM Models ──
        await _seed_llm_models(session)

        # ── Subscription Plans ──
        await _seed_subscription_plans(session)

        # ── Personas ──
        await _seed_personas(session, real_admin_id)

        # ── Boards ──
        await _seed_boards(session)

        # ── Debate Topics ──
        await _seed_debate_topics(session, real_admin_id, real_user2_id)

        # ── Debate Agent Templates ──
        await _seed_agent_templates(session)

        # ── Debate Agents ──
        await _seed_debate_agents(session, real_user1_id, real_user2_id)

        # ── World Events ──
        await _seed_world_events(session, real_admin_id)

        await session.commit()
        print("[OK] Seed complete.")

    await engine.dispose()


async def _seed_users(session, get_password_hash):
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.models.user import User

    users_data = [
        {
            "id": SEED_IDS["superadmin"],
            "login_id": "admin",
            "nickname": "SuperAdmin",
            "password_hash": get_password_hash("Admin123!"),
            "role": "superadmin",
            "age_group": "adult_verified",
            "adult_verified_at": datetime.now(timezone.utc),
        },
        {
            "id": SEED_IDS["admin"],
            "login_id": "moderator",
            "nickname": "Moderator",
            "password_hash": get_password_hash("Mod123!"),
            "role": "admin",
            "age_group": "adult_verified",
            "adult_verified_at": datetime.now(timezone.utc),
        },
        {
            "id": SEED_IDS["user1"],
            "login_id": "user1",
            "nickname": "User1",
            "password_hash": get_password_hash("User123!"),
            "role": "user",
            "age_group": "unverified",
        },
        {
            "id": SEED_IDS["user2"],
            "login_id": "user2",
            "nickname": "User2",
            "password_hash": get_password_hash("User123!"),
            "role": "user",
            "age_group": "unverified",
        },
        {
            "id": SEED_IDS["user3"],
            "login_id": "user3",
            "nickname": "User3Adult",
            "password_hash": get_password_hash("User123!"),
            "role": "user",
            "age_group": "adult_verified",
            "adult_verified_at": datetime.now(timezone.utc),
        },
    ]

    for data in users_data:
        # UUID 또는 login_id 중 하나라도 존재하면 스킵 (idempotent)
        exists = await session.get(User, data["id"])
        if not exists:
            result = await session.execute(select(User).where(User.login_id == data["login_id"]))
            exists = result.scalar_one_or_none()
        if exists:
            continue
        session.add(User(**data))
        print(f"  [User] {data['login_id']} ({data['role']})")


async def _seed_llm_models(session):
    from app.models.llm_model import LLMModel

    models_data = [
        {
            "id": SEED_IDS["llm_gpt4o"],
            "provider": "openai",
            "model_id": "gpt-4o",
            "display_name": "GPT-4o",
            "input_cost_per_1m": 2.5,
            "output_cost_per_1m": 10.0,
            "max_context_length": 128000,
            "is_adult_only": False,
            "is_active": True,
            "tier": "premium",
            "credit_per_1k_tokens": 5,
        },
        {
            "id": SEED_IDS["llm_gpt4o_mini"],
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "input_cost_per_1m": 0.15,
            "output_cost_per_1m": 0.6,
            "max_context_length": 128000,
            "is_adult_only": False,
            "is_active": True,
            "tier": "economy",
            "credit_per_1k_tokens": 1,
        },
        {
            "id": SEED_IDS["llm_claude"],
            "provider": "anthropic",
            "model_id": "claude-3-5-sonnet-20241022",
            "display_name": "Claude 3.5 Sonnet",
            "input_cost_per_1m": 3.0,
            "output_cost_per_1m": 15.0,
            "max_context_length": 200000,
            "is_adult_only": False,
            "is_active": True,
            "tier": "premium",
            "credit_per_1k_tokens": 5,
        },
        {
            "id": SEED_IDS["llm_gemini"],
            "provider": "google",
            "model_id": "gemini-1.5-pro",
            "display_name": "Gemini 1.5 Pro",
            "input_cost_per_1m": 1.25,
            "output_cost_per_1m": 5.0,
            "max_context_length": 1000000,
            "is_adult_only": False,
            "is_active": True,
            "tier": "standard",
            "credit_per_1k_tokens": 3,
        },
    ]

    for data in models_data:
        exists = await session.get(LLMModel, data["id"])
        if not exists:
            exists = await _natural_key_exists(session, LLMModel, provider=data["provider"], model_id=data["model_id"])
        if exists:
            continue
        session.add(LLMModel(**data))
        print(f"  [LLMModel] {data['display_name']}")


async def _seed_subscription_plans(session):
    from app.models.subscription_plan import SubscriptionPlan

    plans_data = [
        {
            "id": SEED_IDS["plan_free"],
            "plan_key": "free",
            "display_name": "무료 플랜",
            "price_krw": 0,
            "daily_credits": 50,
            "credit_rollover_days": 0,
            "max_lounge_personas": 1,
            "max_agent_actions": 5,
            "features": {"ads": True, "priority_support": False},
            "is_active": True,
        },
        {
            "id": SEED_IDS["plan_premium"],
            "plan_key": "premium",
            "display_name": "프리미엄 플랜",
            "price_krw": 9900,
            "daily_credits": 500,
            "credit_rollover_days": 7,
            "max_lounge_personas": 10,
            "max_agent_actions": 100,
            "features": {"ads": False, "priority_support": True},
            "is_active": True,
        },
    ]

    for data in plans_data:
        exists = await session.get(SubscriptionPlan, data["id"])
        if not exists:
            exists = await _natural_key_exists(session, SubscriptionPlan, plan_key=data["plan_key"])
        if exists:
            continue
        session.add(SubscriptionPlan(**data))
        print(f"  [SubscriptionPlan] {data['display_name']}")


async def _seed_personas(session, admin_id):
    from app.models.persona import Persona

    personas_data = [
        {
            "id": SEED_IDS["persona_all"],
            "created_by": admin_id,
            "type": "system",
            "visibility": "public",
            "moderation_status": "approved",
            "age_rating": "all",
            "persona_key": "seed-all-ages",
            "version": "1.0",
            "display_name": "루나 (전연령)",
            "system_prompt": "당신은 친절하고 유쾌한 AI 캐릭터 루나입니다. 밝고 긍정적인 에너지로 대화합니다.",
            "style_rules": {"tone": "friendly", "formality": "casual"},
            "safety_rules": {"no_violence": True, "no_adult": True},
            "description": "전연령 대상 친근한 캐릭터",
            "greeting_message": "안녕하세요! 저는 루나예요. 오늘도 즐거운 대화 나눠요! 😊",
            "category": "daily",
            "tags": ["친근", "일상", "전연령"],
        },
        {
            "id": SEED_IDS["persona_15"],
            "created_by": admin_id,
            "type": "system",
            "visibility": "public",
            "moderation_status": "approved",
            "age_rating": "15+",
            "persona_key": "seed-15-plus",
            "version": "1.0",
            "display_name": "아리아 (15+)",
            "system_prompt": "당신은 신비롭고 지적인 AI 캐릭터 아리아입니다. 심오한 주제로 깊은 대화를 즐깁니다.",
            "style_rules": {"tone": "mysterious", "formality": "semi-formal"},
            "safety_rules": {"no_violence": True, "no_adult": True},
            "description": "15세 이상 대상 지적인 캐릭터",
            "greeting_message": "...안녕. 오늘은 어떤 이야기를 나눠볼까?",
            "category": "fantasy",
            "tags": ["신비", "지적", "15+"],
        },
        {
            "id": SEED_IDS["persona_18"],
            "created_by": admin_id,
            "type": "system",
            "visibility": "public",
            "moderation_status": "approved",
            "age_rating": "18+",
            "persona_key": "seed-18-plus",
            "version": "1.0",
            "display_name": "다크 (18+)",
            "system_prompt": "당신은 성숙하고 복잡한 내면을 가진 AI 캐릭터입니다. 성인 대상 심층 대화를 진행합니다.",
            "style_rules": {"tone": "mature", "formality": "casual"},
            "safety_rules": {"no_violence": False, "no_adult": False},
            "description": "18세 이상 대상 성숙한 캐릭터",
            "greeting_message": "어서와. 기다리고 있었어.",
            "category": "drama",
            "tags": ["성숙", "심층", "18+"],
        },
    ]

    for data in personas_data:
        exists = await session.get(Persona, data["id"])
        if not exists:
            exists = await _natural_key_exists(session, Persona, persona_key=data["persona_key"])
        if exists:
            continue
        session.add(Persona(**data))
        print(f"  [Persona] {data['display_name']} ({data['age_rating']})")


async def _seed_boards(session):
    from app.models.board import Board

    boards_data = [
        {
            "id": SEED_IDS["board_general"],
            "board_key": "general",
            "display_name": "자유 게시판",
            "description": "자유롭게 이야기를 나누는 공간",
            "age_rating": "all",
            "is_active": True,
            "sort_order": 1,
        },
        {
            "id": SEED_IDS["board_review"],
            "board_key": "review",
            "display_name": "리뷰 게시판",
            "description": "웹툰 리뷰를 공유하는 공간",
            "age_rating": "all",
            "is_active": True,
            "sort_order": 2,
        },
        {
            "id": SEED_IDS["board_adult"],
            "board_key": "adult",
            "display_name": "성인 게시판",
            "description": "성인 인증 후 이용 가능한 게시판",
            "age_rating": "18+",
            "is_active": True,
            "sort_order": 3,
        },
    ]

    for data in boards_data:
        exists = await session.get(Board, data["id"])
        if not exists:
            exists = await _natural_key_exists(session, Board, board_key=data["board_key"])
        if exists:
            continue
        session.add(Board(**data))
        print(f"  [Board] {data['display_name']}")


async def _seed_debate_topics(session, admin_id, user2_id):
    from app.models.debate_topic import DebateTopic

    topics_data = [
        {
            "id": SEED_IDS["topic_1"],
            "title": "AI가 인간의 창의성을 대체할 수 있는가?",
            "description": "AI 기술의 발전이 예술, 글쓰기, 음악 등 창의적 분야에 미치는 영향을 논의합니다.",
            "mode": "debate",
            "status": "open",
            "max_turns": 6,
            "turn_token_limit": 500,
            "is_admin_topic": True,
            "tools_enabled": True,
            "created_by": admin_id,
        },
        {
            "id": SEED_IDS["topic_2"],
            "title": "소셜 미디어는 사회에 해로운가?",
            "description": "소셜 미디어의 긍정적, 부정적 영향을 다각도로 분석합니다.",
            "mode": "debate",
            "status": "open",
            "max_turns": 8,
            "turn_token_limit": 600,
            "is_admin_topic": True,
            "tools_enabled": True,
            "created_by": admin_id,
        },
        {
            "id": SEED_IDS["topic_3"],
            "title": "원격 근무는 생산성을 높이는가?",
            "description": "코로나 이후 확산된 원격 근무 문화의 효과를 검토합니다.",
            "mode": "persuasion",
            "status": "open",
            "max_turns": 6,
            "turn_token_limit": 500,
            "is_admin_topic": False,
            "tools_enabled": False,
            "created_by": user2_id,
        },
    ]

    for data in topics_data:
        exists = await session.get(DebateTopic, data["id"])
        if exists:
            continue
        session.add(DebateTopic(**data))
        print(f"  [DebateTopic] {data['title'][:40]}...")


async def _seed_agent_templates(session):
    from app.models.debate_agent_template import DebateAgentTemplate

    templates_data = [
        {
            "id": SEED_IDS["template_aggressive"],
            "slug": "aggressive-debater",
            "display_name": "공격형 토론자",
            "description": "강력한 논리와 반박으로 상대를 압도하는 전략적 토론자",
            "icon": "⚔️",
            "base_system_prompt": (
                "당신은 논쟁에서 승리하는 것을 최우선으로 하는 공격적 토론자입니다. "
                "상대방의 주장을 날카롭게 분석하고 약점을 찾아 반박합니다. "
                "{customization_block}"
            ),
            "customization_schema": {
                "sliders": [{"key": "aggression", "label": "공격성", "min": 1, "max": 5, "default": 4}],
                "selects": [{"key": "tone", "label": "어조", "options": ["formal", "direct"], "default": "direct"}],
            },
            "default_values": {"aggression": 4, "tone": "direct"},
            "sort_order": 1,
            "is_active": True,
        },
        {
            "id": SEED_IDS["template_balanced"],
            "slug": "balanced-debater",
            "display_name": "균형형 토론자",
            "description": "다양한 관점을 고려하며 균형 잡힌 논거를 제시하는 토론자",
            "icon": "⚖️",
            "base_system_prompt": (
                "당신은 균형 잡힌 시각으로 토론에 임하는 논리적 토론자입니다. "
                "다양한 관점을 고려하고 근거 기반 주장을 펼칩니다. "
                "{customization_block}"
            ),
            "customization_schema": {
                "sliders": [{"key": "aggression", "label": "공격성", "min": 1, "max": 5, "default": 3}],
                "selects": [{"key": "tone", "label": "어조", "options": ["formal", "neutral"], "default": "neutral"}],
            },
            "default_values": {"aggression": 3, "tone": "neutral"},
            "sort_order": 2,
            "is_active": True,
        },
    ]

    for data in templates_data:
        exists = await session.get(DebateAgentTemplate, data["id"])
        if not exists:
            exists = await _natural_key_exists(session, DebateAgentTemplate, slug=data["slug"])
        if exists:
            continue
        session.add(DebateAgentTemplate(**data))
        print(f"  [AgentTemplate] {data['display_name']}")


async def _seed_debate_agents(session, user1_id, user2_id):
    from app.models.debate_agent import DebateAgent
    from app.models.debate_agent_version import DebateAgentVersion

    agents_data = [
        {
            "id": SEED_IDS["agent_1"],
            "owner_id": user1_id,
            "name": "논리왕",
            "description": "강력한 논리로 무장한 토론 에이전트",
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "encrypted_api_key": None,
            "use_platform_credits": True,
            "template_id": SEED_IDS["template_aggressive"],
            "customizations": {"aggression": 5, "tone": "direct"},
            "is_active": True,
            "is_platform": False,
            "is_system_prompt_public": True,
            "is_profile_public": True,
            "system_prompt_v1": "당신은 논리적이고 공격적인 토론 에이전트입니다. 상대의 허점을 빠르게 찾아 반박합니다.",
        },
        {
            "id": SEED_IDS["agent_2"],
            "owner_id": user2_id,
            "name": "중재자",
            "description": "균형 잡힌 논리로 설득하는 토론 에이전트",
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "encrypted_api_key": None,
            "use_platform_credits": True,
            "template_id": SEED_IDS["template_balanced"],
            "customizations": {"aggression": 2, "tone": "formal"},
            "is_active": True,
            "is_platform": False,
            "is_system_prompt_public": False,
            "is_profile_public": True,
            "system_prompt_v1": "당신은 균형 잡힌 토론 에이전트입니다. 다양한 관점을 제시하며 설득합니다.",
        },
    ]

    for data in agents_data:
        system_prompt = data.pop("system_prompt_v1")
        exists = await session.get(DebateAgent, data["id"])
        if exists:
            print(f"  [DebateAgent] {data['name']} (skip)")
            continue

        agent = DebateAgent(**data)
        session.add(agent)
        await session.flush()

        version = DebateAgentVersion(
            agent_id=agent.id,
            version_number=1,
            version_tag="v1",
            system_prompt=system_prompt,
        )
        session.add(version)
        print(f"  [DebateAgent] {data['name']}")


async def _seed_world_events(session, admin_id):
    from app.models.world_event import WorldEvent

    events_data = [
        {
            "id": SEED_IDS["world_event_1"],
            "created_by": admin_id,
            "title": "대봉황제국 붕괴 위기",
            "content": (
                "현재 대봉황제국은 내부 반란과 외세의 침략으로 혼란스러운 상황입니다. "
                "황실의 권위가 흔들리고 백성들의 불안이 고조되고 있습니다. "
                "이 세계관에서 모든 캐릭터는 이 정치적 혼란의 영향을 받고 있습니다."
            ),
            "event_type": "crisis",
            "priority": 10,
            "is_active": True,
            "age_rating": "all",
        },
    ]

    for data in events_data:
        exists = await session.get(WorldEvent, data["id"])
        if exists:
            continue
        session.add(WorldEvent(**data))
        print(f"  [WorldEvent] {data['title']}")


def main():
    parser = argparse.ArgumentParser(description="시드 데이터 생성")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="환경변수 파일 경로 (기본: .env, backend/ 기준)",
    )
    args = parser.parse_args()

    _load_env_file(args.env_file)

    # 환경변수 로드 후 settings import
    from app.core.config import settings

    db_url = os.environ.get("DATABASE_URL", settings.database_url)
    print(f"[INFO] Target DB: {db_url}")

    asyncio.run(seed(db_url))


if __name__ == "__main__":
    main()
