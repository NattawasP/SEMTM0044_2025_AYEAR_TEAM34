"""
Data access layer — DuckDB queries for gene lookup, expression, mutations, etc.

Note: Parquet files use categorical encoding for string columns (ach_id, ensembl_id,
hugo_symbol, etc.). DuckDB reads these as DICTIONARY type, which can cause
ConversionErrors with parameterised queries. We CAST to VARCHAR where needed.
"""

import numpy as np
import pandas as pd
from scipy import stats

from app.config import RRF_K
from app.database import query, query_df


# ── Gene queries ──────────────────────────────────────────────

def search_genes(q: str, limit: int = 10) -> list[dict]:
    """Fuzzy search genes by HUGO symbol prefix."""
    return query(
        """
        SELECT DISTINCT
            CAST(hugo_symbol AS VARCHAR) AS hugo_symbol,
            CAST(ensembl_id AS VARCHAR) AS ensembl_id
        FROM dim_genes
        WHERE UPPER(CAST(hugo_symbol AS VARCHAR)) LIKE UPPER(? || '%')
        ORDER BY hugo_symbol
        LIMIT ?
        """,
        [q, limit],
    )


def resolve_gene(hugo: str) -> dict | None:
    """Resolve a HUGO symbol to its Ensembl ID."""
    rows = query(
        """
        SELECT
            CAST(hugo_symbol AS VARCHAR) AS hugo_symbol,
            CAST(ensembl_id AS VARCHAR) AS ensembl_id
        FROM dim_genes
        WHERE UPPER(CAST(hugo_symbol AS VARCHAR)) = UPPER(?)
        LIMIT 1
        """,
        [hugo],
    )
    return rows[0] if rows else None


# ── Expression queries ────────────────────────────────────────

def get_expression_for_gene(ensembl_id: str, source_table: str):
    """Get TPM values for a gene from one expression source. Returns DataFrame."""
    return query_df(
        f"""
        SELECT CAST(ach_id AS VARCHAR) AS ach_id, AVG(tpm) AS tpm
        FROM {source_table}
        WHERE CAST(ensembl_id AS VARCHAR) = ?
        GROUP BY ach_id
        """,
        [ensembl_id],
    )


# ── Protein queries ───────────────────────────────────────────

def get_protein_for_gene(ensembl_id: str):
    """Get protein intensity for a gene. Returns DataFrame."""
    return query_df(
        """
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               AVG(protein_intensity) AS protein_intensity
        FROM fact_proteomics
        WHERE CAST(ensembl_id AS VARCHAR) = ?
        GROUP BY ach_id
        """,
        [ensembl_id],
    )


# ── Mutation queries ──────────────────────────────────────────

def get_mutations_for_gene(ensembl_id: str) -> list[dict]:
    """Get all mutations for a gene."""
    return query(
        """
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               CAST(hugo_symbol AS VARCHAR) AS hugo_symbol,
               chrom, pos, ref, alt,
               variant_type, variant_info, protein_change,
               is_driver, is_hotspot, is_damaging, is_lof, allele_freq
        FROM fact_mutations
        WHERE CAST(ensembl_id AS VARCHAR) = ?
        """,
        [ensembl_id],
    )


def get_mutated_cell_lines(ensembl_id: str) -> set[str]:
    """Get set of ach_ids that have mutations in this gene."""
    rows = query(
        """
        SELECT DISTINCT CAST(ach_id AS VARCHAR) AS ach_id
        FROM fact_mutations
        WHERE CAST(ensembl_id AS VARCHAR) = ?
        """,
        [ensembl_id],
    )
    return {r["ach_id"] for r in rows}


# ── Fusion queries ────────────────────────────────────────────

def get_fusions_for_gene(hugo: str) -> list[dict]:
    """Get fusions involving a gene (as gene1 or gene2), any confidence level.
    Matches on HUGO symbol because the ensg columns in fact_fusions store
    'SYMBOL (ENSG.version)' strings, not bare Ensembl IDs."""
    return query(
        """
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               CAST(gene1_hugo AS VARCHAR) AS gene1_hugo,
               CAST(gene2_hugo AS VARCHAR) AS gene2_hugo,
               fusion_name, ffpm,
               CAST(confidence AS VARCHAR) AS confidence,
               reading_frame, supporting_reads
        FROM fact_fusions
        WHERE (CAST(gene1_hugo AS VARCHAR) = ? OR CAST(gene2_hugo AS VARCHAR) = ?)
        """,
        [hugo, hugo],
    )


def get_fused_cell_lines(hugo: str) -> set[str]:
    """Get set of ach_ids that have fusions involving this gene (any confidence).
    Matches on HUGO symbol (see note in get_fusions_for_gene)."""
    rows = query(
        """
        SELECT DISTINCT CAST(ach_id AS VARCHAR) AS ach_id
        FROM fact_fusions
        WHERE (CAST(gene1_hugo AS VARCHAR) = ? OR CAST(gene2_hugo AS VARCHAR) = ?)
        """,
        [hugo, hugo],
    )
    return {r["ach_id"] for r in rows}

# ── Non-gene-expression exclusion queries ─────────────────────

def get_unstable_cell_lines(msi_max: float | None, cin_max: float | None) -> set[str]:
    """Cell lines exceeding the given genomic instability thresholds.
    signatures_clean.parquet: index=ModelID (ACH IDs), cols: MSIScore, CIN, etc."""
    clauses = []
    params = []
    if msi_max is not None:
        clauses.append("MSIScore > ?")
        params.append(msi_max)
    if cin_max is not None:
        clauses.append("CIN > ?")
        params.append(cin_max)
    if not clauses:
        return set()

    rows = query(
        f"""
        SELECT DISTINCT CAST(ModelID AS VARCHAR) AS ach_id
        FROM fact_signatures
        WHERE {" OR ".join(clauses)}
        """,
        params,
    )
    return {r["ach_id"] for r in rows}


def get_high_metabolite_cell_lines(metabolite: str, threshold: float) -> set[str]:
    """Cell lines whose level of a metabolite exceeds the threshold.
    metabolomics_clean.parquet is wide: cols = CCLE_ID, DepMap_ID, + 225 metabolites."""
    import re
    safe_col = re.sub(r"[^a-zA-Z0-9_ ()/-]", "", metabolite)
    try:
        rows = query(
            f"""
            SELECT DISTINCT CAST(DepMap_ID AS VARCHAR) AS ach_id
            FROM fact_metabolomics
            WHERE "{safe_col}" > ?
            """,
            [threshold],
        )
    except Exception:
        return set()
    return {r["ach_id"] for r in rows}


def get_high_mirna_cell_lines(mirna_id: str, threshold: float) -> set[str]:
    """Cell lines whose expression of a miRNA exceeds the threshold.
    mirna_clean.parquet is transposed: rows = miRNAs, cols = ACH IDs.
    Read with pandas since DuckDB can't easily query this layout."""
    import pandas as pd
    from app.config import PARQUET

    path = PARQUET.get("fact_mirna")
    if path is None or not path.exists():
        return set()

    df = pd.read_parquet(path)
    # Find the string column holding miRNA names
    str_cols = df.select_dtypes(include="object").columns
    if len(str_cols) == 0:
        return set()

    mirna_col = str_cols[0]
    row = df[df[mirna_col] == mirna_id]
    if row.empty:
        return set()

    # Remaining columns are ACH IDs with expression values
    values = row.drop(columns=[mirna_col]).iloc[0]
    return set(values[values > threshold].index.astype(str))


# ── Cell line metadata ────────────────────────────────────────

def get_cell_line(ach_id: str) -> dict | None:
    """Get metadata for a single cell line."""
    rows = query(
        """
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               cell_line_name,
               CAST(primary_disease AS VARCHAR) AS primary_disease,
               CAST(lineage AS VARCHAR) AS lineage,
               CAST(lineage_subtype AS VARCHAR) AS lineage_subtype,
               CAST(sex AS VARCHAR) AS sex,
               CAST(growth_pattern AS VARCHAR) AS growth_pattern
        FROM dim_cell_lines
        WHERE CAST(ach_id AS VARCHAR) = ?
        LIMIT 1
        """,
        [ach_id],
    )
    return rows[0] if rows else None


def get_cell_lines_metadata(ach_ids: list[str]) -> dict[str, dict]:
    """Get metadata for multiple cell lines, returned as {ach_id: {...}}."""
    if not ach_ids:
        return {}
    placeholders = ", ".join(["CAST(? AS VARCHAR)"] * len(ach_ids))
    rows = query(
        f"""
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               cell_line_name,
               CAST(primary_disease AS VARCHAR) AS primary_disease,
               CAST(lineage AS VARCHAR) AS lineage,
               CAST(lineage_subtype AS VARCHAR) AS lineage_subtype,
               CAST(sex AS VARCHAR) AS sex,
               CAST(growth_pattern AS VARCHAR) AS growth_pattern
        FROM dim_cell_lines
        WHERE CAST(ach_id AS VARCHAR) IN ({placeholders})
        """,
        ach_ids,
    )
    return {r["ach_id"]: r for r in rows}


# ── Filter options ────────────────────────────────────────────

def get_diseases() -> list[str]:
    """Get distinct disease values."""
    rows = query(
        """
        SELECT DISTINCT CAST(primary_disease AS VARCHAR) AS primary_disease
        FROM dim_cell_lines
        WHERE primary_disease IS NOT NULL
          AND CAST(primary_disease AS VARCHAR) != ''
        ORDER BY primary_disease
        """
    )
    return [r["primary_disease"] for r in rows if r["primary_disease"]]


def get_lineages() -> list[str]:
    """Get distinct lineage values."""
    rows = query(
        """
        SELECT DISTINCT CAST(lineage AS VARCHAR) AS lineage
        FROM dim_cell_lines
        WHERE lineage IS NOT NULL
          AND CAST(lineage AS VARCHAR) != ''
        ORDER BY lineage
        """
    )
    return [r["lineage"] for r in rows if r["lineage"]]


def get_disease_lineage_mapping() -> list[dict]:
    """Return all distinct (disease, lineage) pairs for linked dropdown filtering."""
    rows = query(
        """
        SELECT DISTINCT
            CAST(primary_disease AS VARCHAR) AS disease,
            CAST(lineage AS VARCHAR) AS lineage
        FROM dim_cell_lines
        WHERE primary_disease IS NOT NULL
          AND CAST(primary_disease AS VARCHAR) != ''
          AND lineage IS NOT NULL
          AND CAST(lineage AS VARCHAR) != ''
        ORDER BY disease, lineage
        """
    )
    return [r for r in rows if r["disease"] and r["lineage"]]


# ── Evidence breakdown (per-source scoring) ──────────────────

EXPRESSION_SOURCES = [
    ("DepMap", "fact_expression_depmap"),
    ("HPA",    "fact_expression_hpa"),
    ("GEO",    "fact_expression_geo"),
]


def get_evidence_for_cell_line(
    ach_id: str,
    genes: list[dict],   # [{"hugo": "EGFR", "ensembl_id": "ENSG...", "direction": "high"}]
) -> dict:
    """
    Compute full evidence breakdown for a single cell line across all queried genes.

    Returns {
        "genes": {
            "EGFR": {
                "direction": "high",
                "sources": [
                    {"source": "DepMap", "tpm": 342.7, "z_score": 2.41,
                     "percentile": 97.8, "z_rank": 3, "pct_rank": 2, "total": 1840},
                    ...
                ],
                "source_count": 3,
                "expression_rank": 2,
                "expression_total": 1840,
            },
            ...
        },
        "protein": {"intensity": 4.82, "z_score": 1.87, "rank": 5, "total": 300},
        "mutations": [...],
        "fusions": [...],
        "data_coverage": {"rna_sources": 3, "has_protein": true, "has_mutations": true, "total_types": 5, "max_types": 5}
    }
    """
    result = {"genes": {}}

    all_mutations = []
    all_fusions = []
    has_protein = False
    total_rna_sources = 0

    for gene in genes:
        ensg = gene["ensembl_id"]
        hugo = gene["hugo"]
        direction = gene.get("direction", "high")
        ascending = direction == "low"

        gene_data = {
            "direction": direction,
            "sources": [],
            "source_count": 0,
            "expression_rank": None,
            "expression_total": 0,
        }

        # Per-source scoring
        rank_dict = {}
        for src_name, src_table in EXPRESSION_SOURCES:
            df = get_expression_for_gene(ensg, src_table)
            if len(df) < 2:
                continue

            tpm_series = df.set_index("ach_id")["tpm"]
            total_cls = len(tpm_series)

            if ach_id not in tpm_series.index:
                continue

            tpm_val = float(tpm_series[ach_id])
            if pd.isna(tpm_val):
                continue

            # Z-score
            z_values = stats.zscore(tpm_series, nan_policy="omit")
            z_series = pd.Series(z_values, index=tpm_series.index) if not isinstance(z_values, pd.Series) else z_values
            z_val = float(z_series[ach_id])

            # Percentile
            pct_series = tpm_series.rank(pct=True, method="average")
            pct_val = float(pct_series[ach_id]) * 100

            # Z-Score rank (rank 1 = best for HIGH, rank 1 = lowest for LOW)
            z_rank_series = z_series.rank(ascending=ascending, method="min")
            z_rank_raw = z_rank_series[ach_id]
            z_rank = int(z_rank_raw) if pd.notna(z_rank_raw) else None

            # Percentile rank
            pct_rank_series = tpm_series.rank(ascending=ascending, method="min")
            pct_rank_raw = pct_rank_series[ach_id]
            pct_rank = int(pct_rank_raw) if pd.notna(pct_rank_raw) else None

            # For RRF ensemble
            rank_dict[f"{src_name}_zscore"] = z_rank_series
            rank_dict[f"{src_name}_percentile"] = pct_rank_series

            gene_data["sources"].append({
                "source": src_name,
                "tpm": round(tpm_val, 2),
                "z_score": round(z_val, 2),
                "percentile": round(pct_val, 1),
                "z_rank": z_rank,
                "pct_rank": pct_rank,
                "total": total_cls,
            })

        gene_data["source_count"] = len(gene_data["sources"])
        if gene_data["source_count"] > total_rna_sources:
            total_rna_sources = gene_data["source_count"]

        # Compute overall expression rank via RRF
        if rank_dict:
            all_ids = set()
            for s in rank_dict.values():
                all_ids.update(s.index)

            rrf_scores = pd.Series(0.0, index=list(all_ids))
            for ranks in rank_dict.values():
                for idx in ranks.index:
                    rank_val = ranks[idx]
                    if pd.notna(rank_val):
                        rrf_scores[idx] += 1.0 / (RRF_K + rank_val)

            rrf_ranked = rrf_scores.rank(ascending=False, method="min")
            if ach_id in rrf_ranked.index:
                rrf_val = rrf_ranked[ach_id]
                gene_data["expression_rank"] = int(rrf_val) if pd.notna(rrf_val) else None
                gene_data["expression_total"] = len(rrf_ranked)

        # Mutations for this gene + cell line
        gene_muts = get_mutations_for_gene(ensg)
        cl_muts = [m for m in gene_muts if m["ach_id"] == ach_id]
        all_mutations.extend(cl_muts)

        # Fusions for this gene + cell line
        gene_fusions = get_fusions_for_gene(hugo)
        cl_fusions = [f for f in gene_fusions if f["ach_id"] == ach_id]
        all_fusions.extend(cl_fusions)

        result["genes"][hugo] = gene_data

    # Protein (use first gene's ensembl_id for protein lookup)
    protein_data = None
    if genes:
        ensg = genes[0]["ensembl_id"]
        prot_df = get_protein_for_gene(ensg)
        if len(prot_df) >= 2:
            intensity_series = prot_df.set_index("ach_id")["protein_intensity"]
            if ach_id in intensity_series.index:
                intensity_val = float(intensity_series[ach_id])
                if pd.notna(intensity_val):
                    has_protein = True
                    total_cls = len(intensity_series)

                    # Z-score
                    z_values = stats.zscore(intensity_series, nan_policy="omit")
                    z_series = pd.Series(z_values, index=intensity_series.index) if not isinstance(z_values, pd.Series) else z_values
                    z_val = float(z_series[ach_id])

                    # Z-score rank
                    z_rank_series = z_series.rank(ascending=False, method="min")
                    z_rank_raw = z_rank_series[ach_id]
                    z_rank = int(z_rank_raw) if pd.notna(z_rank_raw) else None

                    # Percentile
                    pct_series = intensity_series.rank(pct=True, method="average")
                    pct_val = float(pct_series[ach_id]) * 100

                    # Percentile rank
                    pct_rank_series = intensity_series.rank(ascending=False, method="min")
                    pct_rank_raw = pct_rank_series[ach_id]
                    pct_rank = int(pct_rank_raw) if pd.notna(pct_rank_raw) else None

                    protein_data = {
                        "intensity": round(intensity_val, 2),
                        "z_score": round(z_val, 2) if pd.notna(z_val) else None,
                        "z_rank": z_rank,
                        "percentile": round(pct_val, 1) if pd.notna(pct_val) else None,
                        "pct_rank": pct_rank,
                        "rank": z_rank,
                        "total": total_cls,
                    }

    result["protein"] = protein_data
    result["mutations"] = all_mutations
    result["fusions"] = all_fusions

    # Data coverage
    has_mutations = len(all_mutations) > 0
    has_fusions = len(all_fusions) > 0
    total_types = total_rna_sources + (1 if has_protein else 0) + (1 if has_mutations else 0)
    max_types = 3 + 1 + 1  # 3 RNA sources + protein + mutations

    result["data_coverage"] = {
        "rna_sources": total_rna_sources,
        "has_protein": has_protein,
        "has_mutations": has_mutations,
        "has_fusions": has_fusions,
        "total_types": total_types,
        "max_types": max_types,
    }

    return result
