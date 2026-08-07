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
    disease_filter: str | None = Field(None, description="Filter by primary_disease")
    lineage_filter: str | None = Field(None, description="Filter by lineage")
    core_only: bool = Field(False, description="Only cell lines with data in all 3 expression sources")
    top_n: int = Field(20, ge=1, le=200, description="Number of results to return")


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
