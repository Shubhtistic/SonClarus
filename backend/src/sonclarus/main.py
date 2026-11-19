import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from scalar_fastapi import get_scalar_api_reference

from src.sonclarus.api.middleware import CORSMiddlewareWithSettings, log_requests
from src.sonclarus.api.responses import ApiResponse
from src.sonclarus.api.routers import router as api_router
from src.sonclarus.infrastructure.config import get_settings
from src.sonclarus.infrastructure.kafka_client import KafkaProducer
from src.sonclarus.infrastructure.logging_config import setup_logging
from src.sonclarus.infrastructure.redis_client import close_redis, init_redis
from src.sonclarus.infrastructure.s3_client import ensure_bucket_and_cors

# --- logger ---

logger = logging.getLogger(__name__)
setup_logging()


# --- lifespan handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting application (environment=%s)", settings.app.environment)

    logger.info("Checking storage bucket and CORS")
    await ensure_bucket_and_cors()
    logger.info("Storage bootstrap step finished")

    logger.info("Initializing Redis client")
    await init_redis()
    logger.info("Redis client initialized successfully")

    logger.info("Starting Kafka producer")
    await KafkaProducer.start()
    logger.info("Kafka producer started successfully")

    logger.info("Application startup completed")

    try:
        yield
    finally:
        logger.info("Application shutdown initiated")

        logger.info("Stopping Kafka producer")
        await KafkaProducer.stop()
        logger.info("Kafka producer stopped successfully")

        logger.info("Closing Redis client")
        await close_redis()
        logger.info("Redis client closed successfully")

        logger.info("Application shutdown completed")


# --- create app ---
app = FastAPI(lifespan=lifespan)


# --- exception handler ---


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return ApiResponse.error(message=exc.detail, code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return ApiResponse.error(
        message="Validation failed",
        code=422,
        data=None,
        meta={
            "path": str(request.url),
            "errors": exc.errors(),
        },
    )


# --- Cors Middleware Policy ---

settings = get_settings()

app.add_middleware(CORSMiddlewareWithSettings)

if settings.app.environment.lower() != "live":

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        return await log_requests(request, call_next)


# --- imports routers ---

app.include_router(api_router)


# --- scalar docs ---
@app.get("/", include_in_schema=False)
async def scalar():
    return get_scalar_api_reference(openapi_url=app.openapi_url)


# --- simple healthcheck endpoint ---
@app.get("/health")
async def health():
    return ApiResponse.success()
