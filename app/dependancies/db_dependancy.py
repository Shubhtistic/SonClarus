from app.db.database_session import get_db_session
from fastapi import Depends
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession

DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
