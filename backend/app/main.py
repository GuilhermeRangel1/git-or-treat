from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.db.base import Base
from app.middleware.request_limits import RequestLimitsMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.repositories.analytics import AnalyticsSourceUnavailable
from app.services.analytics import AnalyticsAPIError
from app.services.genai_client import GenAIInsightClient, GenAIQuestionClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No PostgreSQL, migrações de schema são gerenciadas pelo Alembic.
    # No caso de SQLite local ou de testes, cria as tabelas automaticamente.
    if settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    timeout = httpx.Timeout(settings.AI_AGENT_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False
    ) as http_client:
        token = (
            settings.AI_AGENT_SERVICE_API_TOKEN.get_secret_value()
            if settings.AI_AGENT_SERVICE_API_TOKEN is not None
            else None
        )
        app.state.genai_question_client = GenAIQuestionClient(
            http_client=http_client,
            base_url=(
                str(settings.AI_AGENT_BASE_URL)
                if settings.AI_AGENT_BASE_URL is not None
                else None
            ),
            service_token=token,
        )
        app.state.genai_insight_client = GenAIInsightClient(
            http_client=http_client,
            base_url=(
                str(settings.AI_AGENT_BASE_URL)
                if settings.AI_AGENT_BASE_URL is not None
                else None
            ),
            service_token=token,
        )
        yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.exception_handler(AnalyticsAPIError)
async def analytics_error_handler(request: Request, exc: AnalyticsAPIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "details": exc.details}
        },
    )


@app.exception_handler(AnalyticsSourceUnavailable)
async def analytics_unavailable_handler(
    request: Request, exc: AnalyticsSourceUnavailable
):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "source_unavailable",
                "message": "A fonte analítica não está configurada.",
                "details": [],
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    if request.url.path == f"{settings.API_V1_STR}/auth/login":
        # Pydantic's default error payload includes rejected input values. The
        # login payload contains a password, so expose locations/messages only.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": error.get("loc", []), "msg": error.get("msg", "Entrada inválida."), "type": error.get("type", "value_error")}
                    for error in exc.errors()
                ]
            },
        )
    from fastapi.exception_handlers import request_validation_exception_handler

    return await request_validation_exception_handler(request, exc)


# Configuração de CORS para permitir requisições do frontend Vite/React
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(RequestLimitsMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.BACKEND_ALLOWED_HOSTS)
app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = uuid4().hex
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# Roteador central v1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Bem-vindo à {settings.PROJECT_NAME}",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
