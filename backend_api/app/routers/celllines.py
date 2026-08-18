"""
Cell line detail and comparison endpoints.
"""

from fastapi import APIRouter, HTTPException, Query

from app.models import CompareRequest, CellLineDetail
from app.services import data_service
from app.services import ranking_service

router = APIRouter(prefix="/api/celllines", tags=["celllines"])


# RNA sources we surface per-source scores for (name shown in UI -> internal source key)
_RNA_SOURCES = [("DepMap", "depmap"), ("HPA", "hpa"), ("GEO", "geo")]


def _per_source_scores(
    ach_id: str,
    gene_targets: list[dict],
    w_rna: float,
    w_protein: float,
) -> dict:
    """
    Compute a per-source combined score for the clicked cell line.

    For each RNA source (DepMap / HPA / GEO) we run the SAME ranking pipeline
    used for the overall score, but with only that one RNA source enabled
    (protein always included). Because it reuses run_ranking(), the resulting
    score is on the same 0-1 scale as the overall score shown at the top of
    the panel. Uses the same RNA/Protein weights the user selected.

    Only returns a score for sources the cell line actually has RNA data in,
    so a source with no data (e.g. no GEO) is omitted rather than showing a
    protein-only value.

    Returns { "DepMap": 0.89, "HPA": 0.85 } (GEO omitted if no data).
    """
    # Which RNA sources does this cell line actually have data in?
    have_sources = set()
    for display_name, src_key in _RNA_SOURCES:
        table = {
            "depmap": "fact_expression_depmap",
            "hpa": "fact_expression_hpa",
            "geo": "fact_expression_geo",
        }[src_key]
        ensg = gene_targets[0]["ensembl_id"]
        df = data_service.get_expression_for_gene(ensg, table)
        if len(df) > 0 and (df["ach_id"] == ach_id).any():
            have_sources.add(src_key)

    result: dict[str, float] = {}

    for display_name, src_key in _RNA_SOURCES:
        # Skip sources this cell line has no RNA data in
        if src_key not in have_sources:
            continue

        try:
            ranked = ranking_service.run_ranking(
                genes=gene_targets,
                w_rna=w_rna,
                w_protein=w_protein,
                mutation_mode="ignore",
                fusion_mode="ignore",
                top_n=100000,                 # no cutoff: we need the clicked cell line
                scoring_method="rrf",
                sources=[src_key, "protein"], # this one RNA source + protein only
            )
        except Exception:
            continue

        for row in ranked:
            if row["ach_id"] == ach_id:
                result[display_name] = row["score"]
                break

    return result


@router.get("/{ach_id}/evidence")
def get_evidence(
    ach_id: str,
    genes: str = Query(..., description="Comma-separated HUGO symbols, e.g. EGFR,TP53"),
    directions: str = Query(..., description="Comma-separated directions matching genes, e.g. high,low"),
    w_rna: float = Query(0.7, description="RNA weight used for per-source scores"),
    w_protein: float = Query(0.3, description="Protein weight used for per-source scores"),
):
    """
    Full evidence breakdown for a cell line: per-source Z-scores, percentiles,
    ranks for each gene, protein z-score, data coverage, and per-source
    combined scores (w_rna*RNA_source + w_protein*Protein, same scale as
    overall score).
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

    # Per-source combined scores (same scale as the overall score), using the
    # user's selected RNA/Protein weights.
    evidence["source_scores"] = _per_source_scores(ach_id, gene_targets, w_rna, w_protein)

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