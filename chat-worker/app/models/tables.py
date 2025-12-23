"""SQLAlchemy table definitions used by the chat worker."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.schema import MetaData

metadata = MetaData()

bots = Table(
    "bots",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("desc", Text, nullable=True),
    Column("is_deleted", Boolean, nullable=False, default=False),
)

provider_configs = Table(
    "provider_configs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("bot_id", UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False),
    Column("provider_id", UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False),
    Column("model_id", UUID(as_uuid=True), ForeignKey("models.id"), nullable=False),
    Column("api_keys", JSONB, nullable=False, default=list),
    Column("config", JSONB, nullable=False, default=dict),
    Column("is_deleted", Boolean, nullable=False, default=False),
)

providers = Table(
    "providers",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slug", String(50), nullable=False),
    Column("api_base_url", String(255), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

models = Table(
    "models",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("pricing", JSONB, nullable=False, default=dict),
    Column("extra_data", JSONB, nullable=False, default=dict),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

__all__ = [
    "metadata",
    "bots",
    "provider_configs",
    "providers",
    "models",
]
