from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.analytics_route import StrictAnalyticsRoute
from app.repositories.analytics import get_analytics_repository
from app.repositories.gold import GoldAnalyticsRepository
from app.schemas.analytics import AnalyticsSource

router = APIRouter(route_class=StrictAnalyticsRoute)


class Neighborhood(BaseModel):
    municipio: str | None
    bairro: str | None


class OptionsData(BaseModel):
    competencias: list[str]
    municipio: list[str]
    bairro: list[str]
    classe: list[str]
    alimentador: list[str]
    bairros: list[Neighborhood]


class OptionsResponse(BaseModel):
    data: OptionsData
    source: AnalyticsSource
    limitations: list[str]


@router.get("/options", response_model=OptionsResponse)
def get_options(repository=Depends(get_analytics_repository)) -> OptionsResponse:
    if isinstance(repository, GoldAnalyticsRepository):
        options = repository.options()
    else:
        from app.synthetic.panorama_fixtures import PANORAMA_RECORDS
        units = repository.units
        options = {key: sorted({row[key] for row in units}) for key in ("municipio", "bairro", "classe", "alimentador")}
        options["bairros"] = [{"municipio": m, "bairro": b} for m, b in sorted({(row["municipio"], row["bairro"]) for row in units})]
        options["competencias"] = sorted({row["competencia"] for row in repository.invoices} | {row["competencia"] for row in PANORAMA_RECORDS})
    return {"data": options, "source": {"kind": repository.source_kind, "version": repository.source_version,
            "is_demo": repository.source_is_demo, "updated_at": repository.source_updated_at},
            "limitations": repository.source_limitations}
