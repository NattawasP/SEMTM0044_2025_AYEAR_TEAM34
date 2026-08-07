"""
Core ranking endpoint — POST /api/rank
"""

from fastapi import APIRouter, HTTPException

from app.models import RankRequest, RankResponse
from app.services import data_service, ranking_service

router = APIRouter(prefix="/api", tags=["ranking"])


@router.post("/rank", response_model=RankResponse)
def rank_cell_lines(req: RankRequest):
    """Run the full ranking pipeline and return ranked cell lines."""
    # Resolve each HUGO symbol → Ensembl ID
    resolved_genes = []
    for gt in req.genes:
        gene = data_service.resolve_gene(gt.hugo)
        if gene is None:
            raise HTTPException(status_code=404, detail=f"Gene '{gt.hugo}' not found")
        resolved_genes.append({
            "hugo": gene["hugo_symbol"],
            "ensembl_id": gene["ensembl_id"],
            "direction": gt.direction,
        })

    results = ranking_service.run_ranking(
        genes=resolved_genes,
        w_rna=req.w_rna,
        w_protein=req.w_protein,
        mutation_mode=req.mutation_mode,
        fusion_mode=req.fusion_mode,
        disease_filter=req.disease_filter,
        lineage_filter=req.lineage_filter,
        core_only=req.core_only,
        top_n=req.top_n,
    )

    return RankResponse(
        query={
            "genes": [{"hugo": g["hugo"], "direction": g["direction"]} for g in resolved_genes],
            "w_rna": req.w_rna,
            "w_protein": req.w_protein,
            "mutation_mode": req.mutation_mode,
            "fusion_mode": req.fusion_mode,
            "disease_filter": req.disease_filter,
            "lineage_filter": req.lineage_filter,
            "core_only": req.core_only,
            "top_n": req.top_n,
        },
        total_results=len(results),
        results=results,
    )
