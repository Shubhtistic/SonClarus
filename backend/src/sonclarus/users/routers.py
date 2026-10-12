from uuid import UUID
from fastapi import APIRouter

from src.sonclarus.shared.responses import ApiResponse
from src.sonclarus.auth.dependencies import CurrentUserDep, VerifiedCurrentUserDep
from src.sonclarus.shared.database import DbSessionDep

from .services import UserService
from .exceptions import UserNotFoundError

# --- router ---
router = APIRouter(prefix="/users", tags=["Users"])


# --- /me for user ----
@router.get("/me")
async def get_user_info(db_session: DbSessionDep, current_user: CurrentUserDep):
    try:
        user_id = UUID(current_user.get("user_id"))
        data = await UserService.get_user_info_by_id(user_id, db_session=db_session)
    except (TypeError, ValueError):
        return ApiResponse.error(message="Invalid token claims", code=401)
    except UserNotFoundError:
        return ApiResponse.error(message="User not found", code=404)

    return ApiResponse.success(message="User fetched Successfully", data=data)


@router.get("/stats")
async def get_user_stats(
    db_session: DbSessionDep, current_verified_user: VerifiedCurrentUserDep
):
    try:
        data = await UserService.get_user_stats(
            current_verified_user, db_session=db_session
        )

    except (TypeError, ValueError):
        return ApiResponse.error(message="Invalid token claims", code=401)

    return ApiResponse.success(message="User Stats Fetched Successfully", data=data)
