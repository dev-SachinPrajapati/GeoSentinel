from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import get_settings

settings = get_settings()

# Build async URL
_raw = settings.DATABASE_URL

def _make_async_url(url: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql+psycopg://", 1)
    return url.replace("+asyncpg", "+psycopg")

_db_url = _make_async_url(_raw)

engine = create_async_engine(
    _db_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize PostGIS extension and tables."""
    import sqlalchemy
    from pathlib import Path

    schema_path = Path(__file__).parent / "schema.sql"

    async with engine.begin() as conn:
        if schema_path.exists():
            # Run the full schema.sql (creates extensions, tables, indexes, views)
            sql = schema_path.read_text()
            await conn.execute(sqlalchemy.text(sql))
        else:
            # Fallback for environments without schema.sql
            await conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            await conn.execute(sqlalchemy.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            await conn.run_sync(Base.metadata.create_all)
            