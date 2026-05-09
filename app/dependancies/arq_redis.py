from arq import create_pool
from arq.connections import RedisSettings
from app.config import settings

# we used from_dsn instead of direct port connection
# because direct port connection assumes connection without ssl
# which may cause issues if redis is configured with ssl
Redis_Settings = RedisSettings.from_dsn(settings.REDIS_URL)


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
    return redis_pool
