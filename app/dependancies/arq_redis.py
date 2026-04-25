from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings

# redis settings
Redis_Settings = RedisSettings(host=settings.REDIS_HOST)
# global variable
redis_pool = None


async def init_redis_pool():
    global redis_pool
    redis_pool = await create_pool(Redis_Settings)


async def close_redis_pool():
    global redis_pool
    # is connection exists
    if redis_pool:
        await redis_pool.close()


async def get_redis_pool():
    global redis_pool
    if not redis_pool:
        raise RuntimeError("Redis pool not initialized")
