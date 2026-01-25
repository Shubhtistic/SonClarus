from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings

engine = create_async_engine(settings.POSTGRES_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)  # A "Session" is a single conversation with the database


async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session
