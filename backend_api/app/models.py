"""
Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field


# ── Request models ────────────────────────────────────────────

class GeneTarget(BaseModel):
    hugo: str = Field(..., description="HUGO gene symbol, e.g. EGFR")
    direction: str = Field("high", pattern="^(high|low)$", description="high = want high expression, low = want low")


class RankRequest(BaseModel):
    genes: list[GeneTarget] = Field(..., min_length=1, description="Target genes with direction")
    w_rna: float = Field(0.7, ge=0.0, le=1.0, description="Weight for RNA expression")
    w_protein: float = Field(0.3, ge=0.0, le=1.0, description="Weight for protein")
    mutation_mode: str = Field("ignore", pattern="^(include|exclude|ignore)$")
    fusion_mode: str = Field("ignore", pattern="^(include|exclude|ignore)$")
    msi_max: float | None = Field(None, description="Exclude cell lines with MSIScore above this")
    cin_max: float | None = Field(None, description="Exclude cell lines with CIN above this")
    exclude_metabolite: str | None = Field(None, description="Metabolite name to filter on")
    metabolite_threshold: float | None = Field(None, description="Exclude above this level; required if exclude_metabolite is set")
    exclude_mirna: str | None = Field(None, description="miRNA id to filter on, e.g. hsa-miR-21")
    mirna_threshold: float | None = Field(None, description="Exclude above this level; required if exclude_mirna is set")
    disease_filter: str | None = Field(None, description="Filter by primary_disease")
    lineage_filter: str | None = Field(None, description="Filter by lineage")
    subtype_filter: str | None = Field(None, description="Filter by Subtype")
    target_disease: str | None = Field(None, description="Preferred disease for Q6 boost")
    target_lineage: str | None = Field(None, description="Preferred lineage for Q6 boost")
    target_subtype: str | None = Field(None, description="Preferred subtype for Q6 boost")
    q6_boost_enabled: bool = Field(True, description="Enable Q6 soft boost (default on)")
    core_only: bool = Field(False, description="Only cell lines with data in all 3 expression sources")
    top_n: int = Field(20, ge=1, le=200, description="Number of results to return")
    scoring_method: str = Field("rrf", pattern="^(rrf|zscore|percentile)$", description="Scoring method: rrf (ensemble), zscore only, percentile only")
    sources: list[str] = Field(
        default=["depmap", "hpa", "geo"],
        description="RNA expression sources to include in ranking: depmap, hpa, geo. Protein is always scored separately (see w_protein)."
    )
    assay_type: str | None = Field(
        None,
        description="Planned assay type for compatibility warnings: adherent_screen, 3d_spheroid, suspension_screen, flexible"
    )


class CompareRequest(BaseModel):
    ach_ids: list[str] = Field(..., min_length=2, description="Cell line IDs to compare")
    gene: str = Field(..., description="Gene to compare across cell lines")


# ── Response models ───────────────────────────────────────────

class GeneInfo(BaseModel):
    hugo_symbol: str
    ensembl_id: str


class GeneSearchResult(BaseModel):
    results: list[GeneInfo]


class RankedCellLine(BaseModel):
    rank: int
    ach_id: str
    cell_line_name: str | None = None
    primary_disease: str | None = None
    lineage: str | None = None
    score: float
    confidence: float
    scenario: str
    growth_pattern: str | None = None
    is_core: bool = False
    mutations: list[dict] | None = None
    fusions: list[dict] | None = None
    q6_score: float | None = None
    match_level: str | None = None
    base_score: float | None = None
    q7_status: str | None = None
    q7_warning: str | None = None


class RankResponse(BaseModel):
    query: dict
    total_results: int
    results: list[RankedCellLine]


class SourceScore(BaseModel):
    source: str
    tpm: float | None = None
    z_score: float | None = None
    percentile: float | None = None
    z_rank: int | None = None
    pct_rank: int | None = None


class CellLineDetail(BaseModel):
    ach_id: str
    cell_line_name: str | None = None
    primary_disease: str | None = None
    lineage: str | None = None
    sex: str | None = None
    growth_pattern: str | None = None
    gene: str
    expression_sources: list[SourceScore]
    protein_intensity: float | None = None
    protein_z_score: float | None = None
    mutations: list[dict]
    fusions: list[dict]
    score: float | None = None
    confidence: float | None = None
    scenario: str | None = None


class FilterOptions(BaseModel):
    values: list[str]
    count: int
