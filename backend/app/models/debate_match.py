import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DebateMatch(Base):
    __tablename__ = "debate_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_topics.id", ondelete="CASCADE"), nullable=False
    )
    agent_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    agent_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    agent_a_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL")
    )
    agent_b_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    # 관리자 강제 매치(테스트) 여부 — True이면 항상 플랫폼 키 사용, ELO 미반영
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    winner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # 스코어카드: {agent_a: {logic: 28, evidence: 22, ...}, agent_b: {...}, reasoning: "..."}
    scorecard: Mapped[dict | None] = mapped_column(JSONB)
    score_a: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    score_b: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    penalty_a: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    penalty_b: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elo_a_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_b_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_a_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elo_b_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 기능 7: 주간 하이라이트
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    featured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 기능 9: 토너먼트 연계
    tournament_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_tournaments.id", ondelete="SET NULL"), nullable=True
    )
    tournament_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 기능 10: 멀티 에이전트 포맷
    format: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'1v1'"))
    # 기능 11: 토론 요약 리포트
    summary_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 시즌 매치: 활성 시즌 진행 중일 때 자동 태깅
    season_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_seasons.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 승급전/강등전 시스템
    match_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ranked")
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("debate_promotion_series.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    topic = relationship("DebateTopic", back_populates="matches")
    agent_a = relationship("DebateAgent", foreign_keys=[agent_a_id])
    agent_b = relationship("DebateAgent", foreign_keys=[agent_b_id])
    agent_a_version = relationship("DebateAgentVersion", foreign_keys=[agent_a_version_id])
    agent_b_version = relationship("DebateAgentVersion", foreign_keys=[agent_b_version_id])
    turns = relationship(
        "DebateTurnLog", back_populates="match", cascade="all, delete-orphan",
        order_by="DebateTurnLog.turn_number"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'error', 'waiting_agent', 'forfeit')",
            name="ck_debate_matches_status",
        ),
        CheckConstraint(
            "match_type IN ('ranked', 'promotion', 'demotion')",
            name="ck_debate_matches_match_type",
        ),
    )


# --- DebateMatchParticipant ---

class DebateMatchParticipant(Base):
    __tablename__ = "debate_match_participants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_matches.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agent_versions.id", ondelete="SET NULL"), nullable=True
    )
    team: Mapped[str] = mapped_column(String(1), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)

    agent = relationship("DebateAgent", foreign_keys=[agent_id])
    version = relationship("DebateAgentVersion", foreign_keys=[version_id])

    __table_args__ = (
        CheckConstraint("team IN ('A', 'B')", name="ck_debate_match_participants_team"),
    )


# --- DebateMatchPrediction ---

class DebateMatchPrediction(Base):
    __tablename__ = "debate_match_predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_matches.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    prediction: Mapped[str] = mapped_column(String(10), nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "prediction IN ('a_win', 'b_win', 'draw')",
            name="ck_debate_match_predictions_prediction",
        ),
        UniqueConstraint("match_id", "user_id", name="uq_debate_match_predictions_user"),
    )


# --- DebateMatchQueue ---

class DebateMatchQueue(Base):
    __tablename__ = "debate_match_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_topics.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("debate_agents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_ready: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # Relationships
    topic = relationship("DebateTopic", back_populates="queue_entries")
    agent = relationship("DebateAgent", foreign_keys=[agent_id])
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("topic_id", "agent_id", name="uq_debate_queue_topic_agent"),
        Index("idx_debate_queue_user_id", "user_id"),
        Index("idx_debate_queue_agent_id", "agent_id"),
    )
