from fastapi import FastAPI
from app.api_routes import ingest, job_status, auth
from scalar_fastapi import get_scalar_api_reference


from app.db.db_models import SQLModel
from app.db.database_session import engine

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    yield


app = FastAPI(title="SonClarus Api", lifespan=lifespan)
app.include_router(auth.router, tags=["Auth"])
app.include_router(ingest.router, tags=["Ingestion"])
app.include_router(job_status.router, tags=["Job Status"])


@app.get("/scalar")
def scalar():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title="SonClarus")
