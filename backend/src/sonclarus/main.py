import logging
from contextlib import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from scalar_fastapi import get_scalar_api_reference
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.sonclarus.shared.logging_config import setup_logging
from src.sonclarus.shared.kafka_client import KafkaProducer
from src.sonclarus.shared.responses import ApiResponse
from src.sonclarus.shared.redis_client import init_redis, close_redis
from src.sonclarus.api.routers import router as api_router
from src.sonclarus.shared.config import get_settings
from src.sonclarus.shared.responses import ApiResponse

# --- logger ---

logger = logging.getLogger(__name__)
setup_logging()


# --- lifespan handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allowed_origins,
    allow_methods=settings.cors.allowed_methods,
    allow_headers=settings.cors.allowed_headers,
    allow_credentials=settings.cors.allow_credentials,
    max_age=settings.cors.max_age,
)


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
