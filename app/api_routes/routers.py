from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    return {"message": "Sonclarus is alive (via Router)"}


@router.get("/status")
def read_status():
    return {"status": "Operational", "mode": "Dev"}
