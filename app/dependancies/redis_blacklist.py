from datetime import datetime, timezone

import redis.asyncio as Redis
from app.config import settings

redis_client = Redis.from_url(settings.REDIS_URL)


async def add_jti_to_blacklist(jti: str, exp: int):

    remaining_time = exp - int(datetime.now(timezone.utc).timestamp())
    if remaining_time <= 0:
        return
    await redis_client.set(f"jti:{jti}", "1", ex=remaining_time + 1)
    # key -> jti:actual_jti
    # value -> just for existenec


async def check_blacklisted_jti(jti: str) -> bool:
    res = await redis_client.get(f"jti:{jti}")
    if res is None:
        # not found
        return False
    return True
