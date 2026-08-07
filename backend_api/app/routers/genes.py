"""
Gene search & resolve endpoints.
"""

from fastapi import APIRouter, Query

from app.services import data_service

router = APIRouter(prefix="/api/genes", tags=["genes"])


@router.get("/search")
def search_genes(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=50)):
    """Autocomplete search for genes by HUGO symbol prefix."""
    results = data_service.search_genes(q, limit)
    return {"results": results}


@router.get("/resolve/{hugo}")
def resolve_gene(hugo: str):
    """Resolve a HUGO symbol to its Ensembl ID."""
    gene = data_service.resolve_gene(hugo)
    if gene is None:
        return {"error": f"Gene '{hugo}' not found", "found": False}
    return {"found": True, **gene}
