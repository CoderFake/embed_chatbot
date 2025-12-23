"""
Database initialization script.
Creates tables and initial root user if they don't exist.
"""
import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.base import Base
from app.models.user import User, UserRole
from app.models.bot import Bot, ProviderConfig, AllowedOrigin
from app.models.document import Document
from app.models.notification import Notification
from app.models.provider import Provider, Model
from app.models.usage import UsageLog
from app.models.visitor import Visitor
from app.config.settings import settings
from app.utils.hasher import get_password_hash
from app.utils.logging import get_logger
from app.utils.datetime_utils import now

logger = get_logger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_database():
    """
    Initialize database schema.
    Creates all tables if they don't exist.
    """
    logger.info("Initializing database schema...")
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Database schema initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        return False


async def create_root_user():
    """
    Create root user if it doesn't exist.
    Uses ROOT_EMAIL and ROOT_PASSWORD from environment variables.
    """
    root_email = settings.ROOT_EMAIL
    root_password = settings.ROOT_PASSWORD
    
    if not root_email or not root_password:
        logger.warning("ROOT_EMAIL or ROOT_PASSWORD not set in environment")
        logger.info("Skipping root user creation")
        return False
    
    logger.info(f"Checking for root user: {root_email}")
    
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": root_email}
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                logger.info(f"Root user already exists: {root_email}")
                return True
            
            logger.info(f"Creating root user: {root_email}")
            
            logger.debug(f"Root password length: {len(root_password)} chars, {len(root_password.encode('utf-8'))} bytes")
            
            try:
                password_hash = get_password_hash(root_password)
                logger.debug(f"Password hashed successfully, hash length: {len(password_hash)}")
            except Exception as hash_err:
                logger.error(f"Password hashing failed: {hash_err}")
                raise
            
            root_user = User(
                email=root_email,
                full_name="Root Administrator",
                password_hash=password_hash,
                role=UserRole.ROOT,
                is_active=True,
                created_at=now(),
                updated_at=now()
            )
            
            session.add(root_user)
            await session.commit()
            
            logger.info(f"Root user created successfully: {root_email}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create root user: {e}", exc_info=True)
        return False


async def init_default_providers():
    """
    Initialize default providers (OpenAI, Gemini, Ollama) if they don't exist.
    Uses DEFAULT_PROVIDERS from settings configuration.
    """
    logger.info("Initializing default providers...")
    
    try:
        async with SessionLocal() as session:
            from sqlalchemy import select
            from app.common.enums import AuthType, ProviderStatus, ModelType
            
            for provider_config in settings.DEFAULT_PROVIDERS:
                result = await session.execute(
                    select(Provider).where(Provider.slug == provider_config["slug"])
                )
                existing_provider = result.scalar_one_or_none()
                
                if existing_provider:
                    logger.info(f"Provider '{provider_config['name']}' already exists")
                    continue
                
                logger.info(f"Creating provider: {provider_config['name']}")
                
                provider = Provider(
                    name=provider_config["name"],
                    slug=provider_config["slug"],
                    api_base_url=provider_config["api_base_url"],
                    auth_type=AuthType(provider_config["auth_type"]),
                    status=ProviderStatus.ACTIVE,
                    extra_data={},
                    created_at=now(),
                    updated_at=now()
                )
                session.add(provider)
                await session.flush()
                
                for model_config in provider_config.get("models", []):
                    logger.info(f"  - Creating model: {model_config['name']}")
                    
                    model = Model(
                        provider_id=provider.id,
                        name=model_config["name"],
                        model_type=ModelType(model_config["model_type"]),
                        context_window=model_config["context_window"],
                        pricing=model_config["pricing"],
                        is_active=True,
                        created_at=now(),
                        updated_at=now()
                    )
                    session.add(model)
                
                await session.commit()
                logger.info(f"Provider '{provider_config['name']}' created with {len(provider_config.get('models', []))} models")
            
            logger.info("Default providers initialized successfully")
            return True
            
    except Exception as e:
        logger.error(f"Failed to initialize default providers: {e}", exc_info=True)
        return False


async def main():
    """
    Main initialization function.
    """
    logger.info("=" * 60)
    logger.info("DATABASE INITIALIZATION")
    logger.info("=" * 60)
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'N/A'}")
    logger.info(f"Timezone: {settings.TIMEZONE}")
    logger.info("=" * 60)
    
    db_success = await init_database()
    if not db_success:
        logger.error("Database initialization failed")
        sys.exit(1)
    
    user_success = await create_root_user()
    if not user_success:
        logger.warning("Root user creation failed or skipped")
    
    providers_success = await init_default_providers()
    if not providers_success:
        logger.warning("Default providers initialization failed or skipped")
    
    logger.info("=" * 60)
    logger.info("INITIALIZATION COMPLETED")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
