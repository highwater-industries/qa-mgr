import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# Determine which database to use based on environment
APP_ENV = os.getenv("APP_ENV", "production")

if APP_ENV == "development":
    DATABASE_URL = os.getenv("DATABASE_URL_TEST")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. "
        "Please create a .env file with DATABASE_URL configured."
    )

# Database engine configuration
# For production, use connection pooling for better performance
# For testing, use NullPool to avoid connection sharing issues
engine_kwargs = {
    "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
    "future": True,
}

if APP_ENV == "test":
    # Use NullPool for tests to ensure isolated connections
    engine_kwargs["poolclass"] = NullPool
else:
    # Production pool configuration
    engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),  # Recycle connections after 1 hour
        "pool_pre_ping": True,  # Verify connections before using them
    })

try:
    engine = create_async_engine(DATABASE_URL, **engine_kwargs)
    logger.info(f"Database engine created for environment: {APP_ENV}")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    expire_on_commit=False,
    class_=AsyncSession
)

async def get_db():
    """Dependency to get database session.
    
    Yields:
        AsyncSession: Database session
        
    Note:
        Session is automatically closed after request completion.
        Transactions are not committed automatically - use commit() explicitly.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()