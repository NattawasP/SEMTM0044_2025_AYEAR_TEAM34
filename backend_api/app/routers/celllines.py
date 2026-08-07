"""
Cell line detail and comparison endpoints.
"""

from fastapi import APIRouter, HTTPException

from app.models import CompareRequest, CellLineDetail
from app.services import data_service

router = APIRouter(prefix="/api/celllines", tags=["celllines"])


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
