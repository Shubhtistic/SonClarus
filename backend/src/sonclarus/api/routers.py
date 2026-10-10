from fastapi import APIRouter

from src.sonclarus.auth.routers import router as auth_router
from src.sonclarus.users.routers import router as user_router
# from src.sonclarus.jobs.routers import router as jobs_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(user_router)
# router.include_router(jobs_router)
