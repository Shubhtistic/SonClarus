from fastapi import FastAPI
from app.api_routes import routers
from scalar_fastapi import get_scalar_api_reference

app = FastAPI()

app.include_router(routers.route)


@app.get("/scalar")
def scalar():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title="SonClarus")
