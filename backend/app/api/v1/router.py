from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    health,
    inspections,
    kpis,
    operations,
    panorama,
    revenue,
    ucs,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(kpis.router, prefix="/kpis", tags=["Indicadores"])
api_router.include_router(panorama.router, prefix="/panorama", tags=["Panorama"])
api_router.include_router(revenue.router, prefix="/revenue", tags=["Receita"])
api_router.include_router(ucs.router, prefix="/ucs", tags=["Unidades Consumidoras"])
api_router.include_router(inspections.router, prefix="/inspections", tags=["Inspeções"])
api_router.include_router(operations.router, prefix="/operations", tags=["Operação / Continuidade"])
api_router.include_router(ai.router, prefix="/ai", tags=["Agente IA"])
api_router.include_router(ai.questions_router, prefix="/ai", tags=["Agente IA"])
