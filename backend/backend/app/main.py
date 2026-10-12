from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core.config import settings
from app.core.logging_config import setup_logging, logger
from app.core.database import init_db
from app.utils.file_utils import ensure_directory

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.courses import router as courses_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.tutor import router as tutor_router
from app.api.routes.assessments import router as assessments_router
from app.api.routes.learner import router as learner_router
from app.api.routes.evaluation import router as evaluation_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup structured logging
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}...")

    # Ensure required directories exist
    ensure_directory(settings.UPLOAD_DIR)

    # Verify production security configuration if in production mode
    if settings.ENVIRONMENT.lower() == "production":
        if "super-secret-key-32b" in settings.JWT_SECRET_KEY or len(settings.JWT_SECRET_KEY) < 32:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: JWT_SECRET_KEY must be explicitly set to a "
                "cryptographically strong secret (at least 32 characters) in production!"
            )
        logger.info("Production security checks passed: Production JWT secret configured and isolated CORS active.")

    # Initialize database tables
    try:
        init_db()
    except Exception as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)

    # Initialize and log LLM service
    try:
        from app.services.llm.llm_service import get_llm_service
        get_llm_service()
    except Exception as e:
        logger.error(f"LLM service initialization error: {e}", exc_info=True)

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME}...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="LearnSphere AI - Grounded Tutor & PDF Ingestion Backend",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Global Exception Handlers
from app.services.llm.llm_service import LLMRateLimitError, LLMTimeoutError

@app.exception_handler(LLMRateLimitError)
async def llm_rate_limit_handler(request: Request, exc: LLMRateLimitError):
    logger.warning(f"LLM rate limit on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "AI service is temporarily busy. Please try again."}
    )

@app.exception_handler(LLMTimeoutError)
async def llm_timeout_handler(request: Request, exc: LLMTimeoutError):
    logger.warning(f"LLM timeout on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={"detail": "AI service is temporarily busy. Please try again."}
    )

# Global Fallback Exception Handler (Hide stack traces in production responses, log server-side)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact the administrator."}
    )

# Include API routes
# Health endpoint available at /health as requested in Section 5
app.include_router(health_router)

# All other API routes mounted under settings.API_PREFIX (/api)
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(courses_router, prefix=settings.API_PREFIX)
app.include_router(uploads_router, prefix=settings.API_PREFIX)
app.include_router(tutor_router, prefix=settings.API_PREFIX)
app.include_router(assessments_router, prefix=settings.API_PREFIX)
app.include_router(learner_router, prefix=settings.API_PREFIX)
app.include_router(evaluation_router, prefix=settings.API_PREFIX)

