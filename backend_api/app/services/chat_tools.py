"""
Chat agent tools — functions the LLM can call via OpenAI function-calling.

Reuses existing DuckDB queries from data_service and database modules
so the chatbot works against the same Parquet data as the main app.
"""

from app.database import query, query_df


# ── Assay profiles (from NattawasP's Q7) ────────────────────

ASSAY_PROFILES = {
    "adherent_screen": {
        "name": "Adherent screen",
        "need_growth": ["Adherent"],
        "description": "Standard drug screens on flat plates",
    },
    "3d_spheroid": {
        "name": "3D spheroid",
        "need_growth": ["Adherent"],
        "description": "Adherent cells that form spheroids",
    },
    "suspension_screen": {
        "name": "Suspension screen",
        "need_growth": ["Suspension"],
        "description": "For blood/lymphoid cells",
    },
    "flexible": {
        "name": "Flexible culture",
        "need_growth": ["Adherent", "Suspension", "Semi-Adherent"],
        "description": "Any growth type is fine",
    },
}


# ── Gene context (AstraZeneca notes) ─────────────────────────

GENE_NOTES = {
    "FGFR2": {
        "has_proteomics": False,
        "has_transcriptomics": True,
        "has_geo": True,
        "notes": "No proteomics data available.",
    },
    "CD86": {
        "has_proteomics": True,
        "has_transcriptomics": True,
        "has_geo": True,
        "notes": "Has proteomics data.",
    },
    "ERBB2": {
        "has_proteomics": True,
        "has_transcriptomics": True,
        "has_geo": True,
        "notes": "Good representation across proteomics, transcriptomics, and GEO.",
    },
    "KLK4": {
        "has_proteomics": False,
        "has_transcriptomics": True,
        "has_geo": True,
        "notes": "No proteomics data. Few cell lines in GEO datasets.",
    },
    "GAPDH": {
        "has_proteomics": True,
        "has_transcriptomics": True,
        "has_geo": True,
        "notes": (
            "HOUSEKEEPING gene used as baseline/control. Activity changes very "
            "little across cells. High expression is expected in most cells and "
            "NOT biologically informative for target selection."
        ),
    },
    "ASGR1": {
        "has_proteomics": True,
        "has_transcriptomics": True,
        "has_geo": False,
        "notes": "Has transcriptomic and proteomic data, but not much GEO data.",
    },
    "MUC1": {
        "has_proteomics": True,
        "has_transcriptomics": False,
        "has_geo": False,
        "notes": "Has proteomic data only.",
    },
    "CD3E": {
        "has_proteomics": False,
        "has_transcriptomics": True,
        "has_geo": False,
        "notes": (
            "T-CELL MARKER. Strong literature evidence for protein expression, "
            "but limited proteomics or GEO cell line data. Expect narrow "
            "expression in immune (T-cell) lineages."
        ),
    },
}


# ── Tool functions ───────────────────────────────────────────

def get_gene_context(gene_symbol: str) -> dict:
    """Get AstraZeneca notes on a target gene."""
    upper = gene_symbol.upper()
    if upper in GENE_NOTES:
        return {"gene": upper, **GENE_NOTES[upper]}
    return {"gene": gene_symbol, "notes": "No AstraZeneca-provided notes for this gene."}


def search_by_lineage(
    lineage: str | None = None,
    disease: str | None = None,
    subtype: str | None = None,
    top_n: int = 10,
) -> list[dict]:
    """
    Search cell lines by lineage, disease, or subtype.
    Returns top N matches ranked by hierarchical match score.
    """
    conditions = []
    params = []

    # Build hierarchical scoring via SQL CASE
    score_parts = []

    if subtype:
        score_parts.append(
            "CASE WHEN UPPER(CAST(lineage_subtype AS VARCHAR)) = UPPER(CAST(? AS VARCHAR)) THEN 1.0 ELSE 0 END"
        )
        params.append(subtype)

    if disease:
        score_parts.append(
            "CASE WHEN UPPER(CAST(primary_disease AS VARCHAR)) = UPPER(CAST(? AS VARCHAR)) THEN 0.75 ELSE 0 END"
        )
        params.append(disease)

    if lineage:
        score_parts.append(
            "CASE WHEN UPPER(CAST(lineage AS VARCHAR)) = UPPER(CAST(? AS VARCHAR)) THEN 0.50 ELSE 0 END"
        )
        params.append(lineage)

    if not score_parts:
        return [{"error": "Provide at least one of lineage, disease, or subtype."}]

    # Use GREATEST to pick highest match level
    score_expr = "GREATEST(" + ", ".join(score_parts) + ")"

    rows = query(
        f"""
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               cell_line_name,
               CAST(lineage AS VARCHAR) AS lineage,
               CAST(primary_disease AS VARCHAR) AS primary_disease,
               CAST(lineage_subtype AS VARCHAR) AS lineage_subtype,
               CAST(growth_pattern AS VARCHAR) AS growth_pattern,
               {score_expr} AS match_score
        FROM dim_cell_lines
        WHERE {score_expr} > 0
        ORDER BY match_score DESC, cell_line_name
        LIMIT ?
        """,
        params + params + [top_n],  # params used twice: once in SELECT, once in WHERE
    )
    return rows


def lookup_cell_line(name_or_id: str) -> dict:
    """Get full metadata for one cell line by name or ACH-ID."""
    if name_or_id.upper().startswith("ACH-"):
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
            [name_or_id],
        )
    else:
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
            WHERE UPPER(cell_line_name) = UPPER(?)
            LIMIT 1
            """,
            [name_or_id],
        )

    if not rows:
        return {"error": f"{name_or_id} not found"}
    return rows[0]


def check_assay_compatibility(cell_names: list[str], assay_type: str) -> list[dict]:
    """Check if cell lines are compatible with an assay type."""
    if not cell_names:
        return [{"error": "cell_names is empty. Call search_by_lineage first."}]

    if assay_type not in ASSAY_PROFILES:
        return [{"error": f"Unknown assay. Choose from: {list(ASSAY_PROFILES.keys())}"}]

    profile = ASSAY_PROFILES[assay_type]
    allowed_growth = profile["need_growth"]

    # Query metadata for the requested cell lines
    placeholders = ", ".join(["CAST(? AS VARCHAR)"] * len(cell_names))
    rows = query(
        f"""
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               cell_line_name,
               CAST(lineage AS VARCHAR) AS lineage,
               CAST(growth_pattern AS VARCHAR) AS growth_pattern
        FROM dim_cell_lines
        WHERE UPPER(cell_line_name) IN ({placeholders})
        """,
        [n.upper() for n in cell_names],
    )

    results = []
    for r in rows:
        gp = r.get("growth_pattern", "unknown") or "unknown"
        # Check if growth pattern matches any allowed pattern (case-insensitive)
        is_ok = any(allowed.lower() in gp.lower() for allowed in allowed_growth)
        status = "OK" if is_ok else "WARN"
        warning = "" if is_ok else f"growth is {gp} (need {'/'.join(allowed_growth)})"

        results.append({
            "cell_line_name": r["cell_line_name"],
            "growth_pattern": gp,
            "assay": profile["name"],
            "status": status,
            "warning": warning,
        })

    return results


def list_options(category: str) -> list[str] | dict:
    """List valid values for a category (lineages, diseases, growth_patterns, assays)."""
    if category == "lineages":
        rows = query(
            """
            SELECT DISTINCT CAST(lineage AS VARCHAR) AS val
            FROM dim_cell_lines
            WHERE lineage IS NOT NULL AND CAST(lineage AS VARCHAR) != ''
            ORDER BY val
            """
        )
        return [r["val"] for r in rows]

    if category == "diseases":
        rows = query(
            """
            SELECT DISTINCT CAST(primary_disease AS VARCHAR) AS val
            FROM dim_cell_lines
            WHERE primary_disease IS NOT NULL AND CAST(primary_disease AS VARCHAR) != ''
            ORDER BY val
            """
        )
        return [r["val"] for r in rows]

    if category == "growth_patterns":
        rows = query(
            """
            SELECT DISTINCT CAST(growth_pattern AS VARCHAR) AS val
            FROM dim_cell_lines
            WHERE growth_pattern IS NOT NULL AND CAST(growth_pattern AS VARCHAR) != ''
            ORDER BY val
            """
        )
        return [r["val"] for r in rows]

    if category == "assays":
        return list(ASSAY_PROFILES.keys())

    return {"error": f"Unknown category: {category}"}
