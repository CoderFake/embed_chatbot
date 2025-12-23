"""SQLAlchemy table definitions for database access."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Numeric, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID, INET
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

visitors = Table(
    "visitors",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("bot_id", UUID(as_uuid=True), ForeignKey("bots.id")),
    Column("ip_address", INET, nullable=True),
    Column("name", String(50), nullable=True),
    Column("address", String(255), nullable=True),
    Column("phone", String(255), nullable=True),
    Column("email", String(100), nullable=True),
    Column("lead_score", Integer, nullable=False, default=0),
    Column("lead_assessment", JSONB, nullable=False, default=dict),
)

chat_sessions = Table(
    "chat_sessions",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("bot_id", UUID(as_uuid=True), ForeignKey("bots.id")),
    Column("visitor_id", UUID(as_uuid=True), ForeignKey("visitors.id")),
    Column("session_token", String(255), nullable=False),
    Column("extra_data", JSONB, nullable=False, default=dict),
)

chat_messages = Table(
    "chat_messages",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("session_id", UUID(as_uuid=True), ForeignKey("chat_sessions.id")),
    Column("query", Text, nullable=True),
    Column("response", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
)

provider_configs = Table(
    "provider_configs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("bot_id", UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False),
    Column("provider_id", UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False),
    Column("model_id", UUID(as_uuid=True), ForeignKey("models.id"), nullable=True),
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
    Column("pricing", Numeric(10, 6), nullable=True),
    Column("extra_data", JSONB, nullable=True, default=dict),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
)

__all__ = [
    "metadata",
    "bots",
    "visitors",
    "chat_sessions",
    "chat_messages",
    "provider_configs",
    "providers",
    "models",
]
