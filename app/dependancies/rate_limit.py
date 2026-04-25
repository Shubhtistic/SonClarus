from fastapi import HTTPException, status
import redis.asyncio as AsyncRedis
from app.config import settings
from app.dependancies.auth import CurrentUserDep

redis_client = AsyncRedis.from_url(settings.REDIS_URL, decode_responses=True)


def check_limit(limit: int, window_seconds: int = 60):
    async def _check_limit(user_id: CurrentUserDep):

        if not user_id:
            return

        redis_key = f"rate_limit:{user_id}"
        # create a key

        # increment key
        curr_count = await redis_client.incr(redis_key)

        # if first time
        if curr_count == 1:
            await redis_client.expire(redis_key, window_seconds)

        elif curr_count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"You have the exceeded the rate limit set for this api please wait a bit ....",
            )

    # return this inner function
    return _check_limit
