"""
Cell line detail and comparison endpoints.
"""

from fastapi import APIRouter, HTTPException, Query

from app.models import CompareRequest, CellLineDetail
from app.services import data_service

router = APIRouter(prefix="/api/celllines", tags=["celllines"])


@router.get("/{ach_id}/evidence")
def get_evidence(
    ach_id: str,
    genes: str = Query(..., description="Comma-separated HUGO symbols, e.g. EGFR,TP53"),
    directions: str = Query(..., description="Comma-separated directions matching genes, e.g. high,low"),
):
    """
    Full evidence breakdown for a cell line: per-source Z-scores, percentiles,
    ranks for each gene, protein z-score, data coverage.
    """
    cl = data_service.get_cell_line(ach_id)
    if cl is None:
        raise HTTPException(status_code=404, detail=f"Cell line '{ach_id}' not found")

    hugo_list = [g.strip() for g in genes.split(",") if g.strip()]
    dir_list = [d.strip() for d in directions.split(",") if d.strip()]

    if len(hugo_list) != len(dir_list):
        raise HTTPException(status_code=400, detail="genes and directions must have the same number of items")

    # Resolve all genes
    gene_targets = []
    for hugo, direction in zip(hugo_list, dir_list):
        info = data_service.resolve_gene(hugo)
        if info is None:
            raise HTTPException(status_code=404, detail=f"Gene '{hugo}' not found")
        gene_targets.append({
            "hugo": info["hugo_symbol"],
            "ensembl_id": info["ensembl_id"],
            "direction": direction,
        })

    evidence = data_service.get_evidence_for_cell_line(ach_id, gene_targets)

    return {**cl, **evidence}


@router.get("/{ach_id}")
def get_cell_line(ach_id: str, gene: str | None = None):
    """
    Get detail view for a single cell line.
    If gene is provided, includes expression, protein, mutation, and fusion data for that gene.
    """
    cl = data_service.get_cell_line(ach_id)
    if cl is None:
        raise HTTPException(status_code=404, detail=f"Cell line '{ach_id}' not found")

    result = {**cl}

    if gene:
        gene_info = data_service.resolve_gene(gene)
        if gene_info is None:
            raise HTTPException(status_code=404, detail=f"Gene '{gene}' not found")

        ensg = gene_info["ensembl_id"]

        # Expression per source
        expression_sources = []
        for src_name, src_table in [
            ("DepMap", "fact_expression_depmap"),
            ("HPA", "fact_expression_hpa"),
            ("GEO", "fact_expression_geo"),
        ]:
            df = data_service.get_expression_for_gene(ensg, src_table)
            match = df[df["ach_id"] == ach_id]
            if len(match) > 0:
                expression_sources.append({
                    "source": src_name,
                    "tpm": round(float(match["tpm"].iloc[0]), 4),
                })

        # Protein
        prot_df = data_service.get_protein_for_gene(ensg)
        prot_match = prot_df[prot_df["ach_id"] == ach_id]
        protein_intensity = round(float(prot_match["protein_intensity"].iloc[0]), 4) if len(prot_match) > 0 else None

        # Mutations
        all_muts = data_service.get_mutations_for_gene(ensg)
        mutations = [m for m in all_muts if m["ach_id"] == ach_id]

        # Fusions
        all_fusions = data_service.get_fusions_for_gene(ensg)
        fusions = [f for f in all_fusions if f["ach_id"] == ach_id]

        result["gene"] = gene
        result["expression_sources"] = expression_sources
        result["protein_intensity"] = protein_intensity
        result["mutations"] = mutations
        result["fusions"] = fusions

    return result


@router.post("/compare")
def compare_cell_lines(req: CompareRequest):
    """
    Side-by-side comparison of cell lines for a given gene.
    Returns expression, protein, mutation data for each ach_id.
    """
    gene_info = data_service.resolve_gene(req.gene)
    if gene_info is None:
        raise HTTPException(status_code=404, detail=f"Gene '{req.gene}' not found")

    ensg = gene_info["ensembl_id"]
    comparisons = []

    for ach_id in req.ach_ids:
        cl = data_service.get_cell_line(ach_id)
        if cl is None:
            continue

        # Expression per source
        expression_sources = []
        for src_name, src_table in [
            ("DepMap", "fact_expression_depmap"),
            ("HPA", "fact_expression_hpa"),
            ("GEO", "fact_expression_geo"),
        ]:
            df = data_service.get_expression_for_gene(ensg, src_table)
            match = df[df["ach_id"] == ach_id]
            if len(match) > 0:
                expression_sources.append({
                    "source": src_name,
                    "tpm": round(float(match["tpm"].iloc[0]), 4),
                })

        # Protein
        prot_df = data_service.get_protein_for_gene(ensg)
        prot_match = prot_df[prot_df["ach_id"] == ach_id]
        protein_intensity = round(float(prot_match["protein_intensity"].iloc[0]), 4) if len(prot_match) > 0 else None

        # Mutations
        all_muts = data_service.get_mutations_for_gene(ensg)
        mutations = [m for m in all_muts if m["ach_id"] == ach_id]

        comparisons.append({
            **cl,
            "gene": req.gene,
            "expression_sources": expression_sources,
            "protein_intensity": protein_intensity,
            "mutations": mutations,
        })

    return {"gene": req.gene, "comparisons": comparisons}
