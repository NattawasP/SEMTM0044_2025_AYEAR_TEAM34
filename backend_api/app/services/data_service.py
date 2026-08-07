"""
Data access layer — DuckDB queries for gene lookup, expression, mutations, etc.

Note: Parquet files use categorical encoding for string columns (ach_id, ensembl_id,
hugo_symbol, etc.). DuckDB reads these as DICTIONARY type, which can cause
ConversionErrors with parameterised queries. We CAST to VARCHAR where needed.
"""

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

def get_fusions_for_gene(ensembl_id: str) -> list[dict]:
    """Get fusions involving a gene (as gene1 or gene2), high/medium confidence only."""
    return query(
        """
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               CAST(gene1_hugo AS VARCHAR) AS gene1_hugo,
               CAST(gene2_hugo AS VARCHAR) AS gene2_hugo,
               fusion_name, ffpm,
               CAST(confidence AS VARCHAR) AS confidence,
               reading_frame, supporting_reads
        FROM fact_fusions
        WHERE (CAST(gene1_ensg AS VARCHAR) = ? OR CAST(gene2_ensg AS VARCHAR) = ?)
          AND CAST(confidence AS VARCHAR) IN ('high', 'medium')
        """,
        [ensembl_id, ensembl_id],
    )


def get_fused_cell_lines(ensembl_id: str) -> set[str]:
    """Get set of ach_ids that have fusions involving this gene."""
    rows = query(
        """
        SELECT DISTINCT CAST(ach_id AS VARCHAR) AS ach_id
        FROM fact_fusions
        WHERE (CAST(gene1_ensg AS VARCHAR) = ? OR CAST(gene2_ensg AS VARCHAR) = ?)
          AND CAST(confidence AS VARCHAR) IN ('high', 'medium')
        """,
        [ensembl_id, ensembl_id],
    )
    return {r["ach_id"] for r in rows}


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
        ORDER BY primary_disease
        """
    )
    return [r["primary_disease"] for r in rows]


def get_lineages() -> list[str]:
    """Get distinct lineage values."""
    rows = query(
        """
        SELECT DISTINCT CAST(lineage AS VARCHAR) AS lineage
        FROM dim_cell_lines
        WHERE lineage IS NOT NULL
        ORDER BY lineage
        """
    )
    return [r["lineage"] for r in rows]
