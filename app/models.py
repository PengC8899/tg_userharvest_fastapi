from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import get_settings


Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, index=True, nullable=False)
    phone = Column(String(64), nullable=True)
    session_string = Column(Text, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    title = Column(String(256), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", name="uq_group_account_chat"),
        Index("ix_group_chat_id", "chat_id"),
        Index("ix_group_title", "title"),
    )


class SelectedGroup(Base):
    __tablename__ = "selected_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", name="uq_selected_account_chat"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(64), index=True, nullable=True)
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    is_bot = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Speak(Base):
    __tablename__ = "speaks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    tg_user_id = Column(BigInteger, ForeignKey("users.tg_user_id", ondelete="CASCADE"), nullable=False)
    message_id = Column(Integer, nullable=False)
    message_date = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "chat_id", "tg_user_id", "message_id", name="uq_speak_unique"),
        Index("ix_speak_account", "account_id"),
        Index("ix_speak_chat", "chat_id"),
        Index("ix_speak_date", "message_date"),
        Index("ix_speak_user", "tg_user_id"),
    )


class CollectionProgress(Base):
    __tablename__ = "collection_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, unique=True)
    current_group = Column(Integer, default=0, nullable=False)
    total_groups = Column(Integer, default=0, nullable=False)
    percentage = Column(Integer, default=0, nullable=False)
    group_name = Column(String(256), default="准备中...", nullable=False)
    status = Column(String(32), default="preparing", nullable=False)  # preparing, collecting, completed, error
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_progress_account", "account_id"),
        Index("ix_progress_status", "status"),
    )


_engine = None
SessionLocal = None


def _init_engine_and_session():
    global _engine, SessionLocal
    if _engine is not None:
        return
    settings = get_settings()
    _engine = create_engine(settings.db_url, future=True)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(_engine)


def get_db():
    _init_engine_and_session()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()