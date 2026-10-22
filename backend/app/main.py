from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.db.base import Base
from app.core.database import engine
from app.api.v1.router import api_router
from app.repositories.analytics import AnalyticsSourceUnavailable
from app.services.analytics import AnalyticsAPIError
from app.middleware.request_limits import RequestLimitsMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No PostgreSQL, migrações de schema são gerenciadas pelo Alembic.
    # No caso de SQLite local ou de testes, cria as tabelas automaticamente.
    if settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
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
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


@app.exception_handler(AnalyticsSourceUnavailable)
async def analytics_unavailable_handler(request: Request, exc: AnalyticsSourceUnavailable):
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "source_unavailable", "message": "A fonte analítica não está configurada.", "details": []}},
    )



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

# Roteador central v1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Bem-vindo à {settings.PROJECT_NAME}",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
