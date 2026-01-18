from fastapi import APIRouter

route = APIRouter()


@route.get("/")
def root():
    return {"message": "Sonclarus is alive (via Router)"}


@route.get("/status")
def read_status():
    return {"status": "Operational", "mode": "Dev"}
