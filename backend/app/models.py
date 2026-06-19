import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    extractions: Mapped[list["Extraction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    input_type: Mapped[str] = mapped_column(String(20), nullable=False, default="paste")

    merchant: Mapped[str | None] = mapped_column(String(255))
    document_type: Mapped[str | None] = mapped_column(String(30))
    amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(10), default="USD")
    purchase_date: Mapped[date | None] = mapped_column(Date)
    subscription_status: Mapped[str | None] = mapped_column(String(20))
    renewal_date: Mapped[date | None] = mapped_column(Date)
    free_trial_end_date: Mapped[date | None] = mapped_column(Date)
    return_deadline: Mapped[date | None] = mapped_column(Date)
    cancellation_deadline: Mapped[date | None] = mapped_column(Date)
    warranty_end_date: Mapped[date | None] = mapped_column(Date)
    cancellation_policy: Mapped[str | None] = mapped_column(Text)
    refund_opportunity: Mapped[str | None] = mapped_column(Text)
    price_increased: Mapped[bool | None] = mapped_column(Boolean)
    old_price: Mapped[float | None] = mapped_column(Float)
    new_price: Mapped[float | None] = mapped_column(Float)
    detected_risk: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(String(50))
    explanation: Mapped[str | None] = mapped_column(Text)

    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("extractions.id", ondelete="SET NULL")
    )

    confidence_score: Mapped[float | None] = mapped_column(Float)
    field_confidences: Mapped[str | None] = mapped_column(Text)
    raw_llm_response: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    user: Mapped["User"] = relationship(back_populates="extractions")
    action_cards: Mapped[list["ActionCard"]] = relationship(
        back_populates="extraction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_extractions_user_hash", "user_id", "content_hash"),
    )


class ActionCard(Base):
    __tablename__ = "action_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    extraction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("extractions.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    reminder_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    savings_amount: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    user: Mapped["User"] = relationship()
    extraction: Mapped["Extraction"] = relationship(back_populates="action_cards")
    email_draft: Mapped["EmailDraft | None"] = relationship(
        back_populates="action_card", cascade="all, delete-orphan", uselist=False
    )


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_card_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("action_cards.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    user_edited_body: Mapped[str | None] = mapped_column(Text)
    copied: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_llm_response: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    user: Mapped["User"] = relationship()
    action_card: Mapped["ActionCard"] = relationship(back_populates="email_draft")
