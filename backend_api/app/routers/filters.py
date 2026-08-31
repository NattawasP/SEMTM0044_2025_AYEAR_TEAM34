"""
Filter option endpoints — populate disease/lineage dropdowns.
"""

from fastapi import APIRouter

from app.models import FilterOptions
from app.services import data_service

router = APIRouter(prefix="/api/filters", tags=["filters"])


@router.get("/diseases", response_model=FilterOptions)
def list_diseases():
    """Return all distinct disease values for the dropdown."""
    values = data_service.get_diseases()
    return FilterOptions(values=values, count=len(values))


@router.get("/lineages", response_model=FilterOptions)
def list_lineages():
    """Return all distinct lineage values for the dropdown."""
    values = data_service.get_lineages()
    return FilterOptions(values=values, count=len(values))


@router.get("/disease-lineage-mapping")
def disease_lineage_mapping():
    """Return all (disease, lineage) pairs for linked dropdown filtering."""
    pairs = data_service.get_disease_lineage_mapping()
    return {"pairs": pairs}
