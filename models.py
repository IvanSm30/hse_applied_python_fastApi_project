from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    telegram_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True)
    display_name = Column(String)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)


class Link(Base):
    __tablename__ = "links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    short_code = Column(String(10), unique=True, index=True)
    original_url = Column(Text, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    is_anonymous = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    click_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True))
    deleted_at = Column(DateTime(timezone=True))
