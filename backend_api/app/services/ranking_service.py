"""
Core ranking algorithm.

Pipeline:
  1. Expression ranking: Z-Score + Percentile per source → RRF ensemble
  2. Protein ranking: Z-Score + Percentile → RRF
  3. Combined RNA + Protein (4 scenarios, configurable weights)
  4. Mutation/Fusion hard filter (include/exclude/ignore)
  5. Multi-gene combination via RRF
  6. Optional post-filters (disease, lineage, core-only)

Note on RRF averaging:
  When fusing the per-source expression ranks, we AVERAGE the RRF contributions
  (divide by the number of rank lists that actually cover each cell line) instead
  of summing them. This prevents cell lines that are missing a data source (e.g.
  no GEO) from being penalised: a cell line with very high RNA in the 2 sources
  it has is judged on the quality of those ranks, not on how many sources exist.
  Coverage is surfaced separately (source_count / is_core) so users who want
  multi-source validation can filter for it instead of it being baked into score.
"""

import numpy as np
import pandas as pd
from scipy import stats

from app.config import RRF_K
from app.services import data_service


# ── Statistical helpers ───────────────────────────────────────

def _zscore_rank(series: pd.Series) -> pd.Series:
    """Z-score normalise, then rank descending (rank 1 = highest z-score)."""
    z = stats.zscore(series, nan_policy="omit")
    return pd.Series(z, index=series.index).rank(ascending=False, method="min")


def _percentile_rank(series: pd.Series) -> pd.Series:
    """Percentile rank, then rank descending (rank 1 = highest percentile)."""
    pct = series.rank(pct=True, method="average")
    return pct.rank(ascending=False, method="min")


def _rrf(rank_dict: dict[str, pd.Series], k: int = RRF_K, average: bool = False) -> pd.Series:
    """
    Reciprocal Rank Fusion across multiple rank Series.

    average=False (default): raw sum of 1/(k+rank) — used for multi-gene fusion.
    average=True: divide each cell line's summed score by the number of rank
                  lists that actually covered it. This makes cell lines with
                  fewer data sources comparable to those with more, so a strong
                  cell line missing one source is not pushed down the ranking.
    """
    all_ids: set[str] = set()
    for s in rank_dict.values():
        all_ids.update(s.index)

    scores = pd.Series(0.0, index=list(all_ids))
    counts = pd.Series(0, index=list(all_ids))
    for ranks in rank_dict.values():
        for idx in ranks.index:
            scores[idx] += 1.0 / (k + ranks[idx])
            counts[idx] += 1

    if average:
        # Avoid division by zero; counts is >= 1 wherever scores was touched.
        counts = counts.replace(0, 1)
        scores = scores / counts

    return scores


def _norm01(s: pd.Series) -> pd.Series:
    """Min-max normalise to [0, 1]."""
    if len(s) == 0:
        return s
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


# ── Expression ranking for one gene ──────────────────────────

EXPRESSION_SOURCES = [
    ("depmap", "fact_expression_depmap"),
    ("hpa",    "fact_expression_hpa"),
    ("geo",    "fact_expression_geo"),
]


def rank_expression(
    ensembl_id: str,
    scoring_method: str = "rrf",
    enabled_sources: list[str] | None = None,
) -> tuple[pd.Series, pd.Series]:
    """
    Compute expression ranking for one gene.
    scoring_method: "rrf" (z-score + percentile ensemble), "zscore" only, "percentile" only.
    enabled_sources: list of source names to include (e.g. ["depmap", "hpa", "geo"]).
                     None means all sources.
    Returns (scores indexed by ach_id, source_coverage Series).
    """
    rank_dict: dict[str, pd.Series] = {}
    source_presence: dict[str, set[str]] = {}

    for src_name, src_table in EXPRESSION_SOURCES:
        # Skip sources not selected by the user
        if enabled_sources is not None and src_name not in enabled_sources:
            continue

        df = data_service.get_expression_for_gene(ensembl_id, src_table)
        if len(df) < 2:
            continue

        tpm = df.set_index("ach_id")["tpm"]

        if scoring_method in ("rrf", "zscore"):
            rank_dict[f"{src_name}_zscore"] = _zscore_rank(tpm)
        if scoring_method in ("rrf", "percentile"):
            rank_dict[f"{src_name}_percentile"] = _percentile_rank(tpm)

        for ach in tpm.index:
            source_presence.setdefault(ach, set()).add(src_name)

    if not rank_dict:
        return pd.Series(dtype=float), pd.Series(dtype=int)

    # Average RRF across source/method rank lists so cell lines with fewer
    # sources are not penalised for missing data.
    rrf = _rrf(rank_dict, average=True)
    coverage = pd.Series({ach: len(srcs) for ach, srcs in source_presence.items()})
    return rrf, coverage


# ── Protein ranking for one gene ─────────────────────────────

def rank_protein(ensembl_id: str) -> pd.Series:
    """Compute RRF protein score for one gene."""
    df = data_service.get_protein_for_gene(ensembl_id)
    if len(df) < 2:
        return pd.Series(dtype=float)

    intensity = df.set_index("ach_id")["protein_intensity"]
    rank_dict = {
        "protein_zscore": _zscore_rank(intensity),
        "protein_percentile": _percentile_rank(intensity),
    }
    # Protein has a single source; averaging vs summing gives the same ordering,
    # but we average for consistency with the expression side.
    return _rrf(rank_dict, average=True)


# ── Combine RNA + Protein (4 scenarios) ──────────────────────

def combine_rna_protein(
    expr_rrf: pd.Series,
    prot_rrf: pd.Series,
    w_rna: float,
    w_prot: float,
) -> pd.DataFrame:
    """
    Combine expression and protein RRF scores.
    Returns DataFrame with: ach_id, combined_score, scenario, coverage_confidence.
    """
    expr_norm = _norm01(expr_rrf)
    prot_norm = _norm01(prot_rrf)
    all_ids = set(expr_norm.index) | set(prot_norm.index)

    rows = []
    for ach in all_ids:
        if ach is None or (isinstance(ach, float) and np.isnan(ach)):
            continue
        has_rna = ach in expr_norm.index and not np.isnan(expr_norm.get(ach, np.nan))
        has_prot = ach in prot_norm.index and not np.isnan(prot_norm.get(ach, np.nan))

        if has_rna and has_prot:
            score = w_rna * expr_norm[ach] + w_prot * prot_norm[ach]
            scenario = "RNA+Protein"
            confidence = 1.0
        elif has_rna:
            score = w_rna * float(expr_norm[ach])
            scenario = "RNA only"
            confidence = w_rna
        elif has_prot:
            score = w_prot * float(prot_norm[ach])
            scenario = "Protein only"
            confidence = w_prot
        else:
            continue

        rows.append({
            "ach_id": ach,
            "combined_score": score,
            "scenario": scenario,
            "coverage_confidence": confidence,
        })

    return pd.DataFrame(rows)


# ── Mutation / Fusion hard filters ───────────────────────────

def apply_mutation_filter(
    df: pd.DataFrame, mode: str, ensembl_id: str
) -> pd.DataFrame:
    """Apply hard mutation filter: include / exclude / ignore."""
    if mode == "ignore":
        return df
    mutated = data_service.get_mutated_cell_lines(ensembl_id)
    if not mutated:
        return df if mode == "exclude" else df.iloc[0:0]  # include with no mutations = empty

    if mode == "include":
        return df[df["ach_id"].isin(mutated)]
    else:  # exclude
        return df[~df["ach_id"].isin(mutated)]


def apply_fusion_filter(
    df: pd.DataFrame, mode: str, hugo: str
) -> pd.DataFrame:
    """Apply hard fusion filter: include / exclude / ignore.
    Matches fusion rows by HUGO symbol (see get_fused_cell_lines)."""
    if mode == "ignore":
        return df
    fused = data_service.get_fused_cell_lines(hugo)
    if not fused:
        return df if mode == "exclude" else df.iloc[0:0]

    if mode == "include":
        return df[df["ach_id"].isin(fused)]
    else:
        return df[~df["ach_id"].isin(fused)]

# ── Instability / Metabolite / miRNA filters ───────────────────────────

def apply_instability_filter(
    df: pd.DataFrame, msi_max: float | None, cin_max: float | None
) -> pd.DataFrame:
    """Exclude cell lines above the given MSI / CIN thresholds."""
    if msi_max is None and cin_max is None:
        return df
    unstable = data_service.get_unstable_cell_lines(msi_max, cin_max)
    return df[~df["ach_id"].isin(unstable)] if unstable else df


def apply_metabolite_filter(
    df: pd.DataFrame, metabolite: str | None, threshold: float | None
) -> pd.DataFrame:
    """Exclude cell lines whose level of a metabolite exceeds the threshold."""
    if metabolite is None or threshold is None:
        return df
    high = data_service.get_high_metabolite_cell_lines(metabolite, threshold)
    return df[~df["ach_id"].isin(high)] if high else df


def apply_mirna_filter(
    df: pd.DataFrame, mirna_id: str | None, threshold: float | None
) -> pd.DataFrame:
    """Exclude cell lines whose expression of a miRNA exceeds the threshold."""
    if mirna_id is None or threshold is None:
        return df
    high = data_service.get_high_mirna_cell_lines(mirna_id, threshold)
    return df[~df["ach_id"].isin(high)] if high else df


# ── Full ranking pipeline ────────────────────────────────────

def run_ranking(
    genes: list[dict],       # [{"hugo": "EGFR", "direction": "high", "ensembl_id": "ENSG..."}]
    w_rna: float = 0.7,
    w_protein: float = 0.3,
    mutation_mode: str = "ignore",
    fusion_mode: str = "ignore",
    msi_max: float | None = None,
    cin_max: float | None = None,
    exclude_metabolite: str | None = None,
    metabolite_threshold: float | None = None,
    exclude_mirna: str | None = None,
    mirna_threshold: float | None = None,
    disease_filter: str | None = None,
    lineage_filter: str | None = None,
    core_only: bool = False,
    top_n: int = 20,
    scoring_method: str = "rrf",
    sources: list[str] | None = None,
    assay_type: str | None = None,
) -> list[dict]:
    """
    Execute the full ranking pipeline. Returns list of ranked cell line dicts.
    """
    # Per-gene scoring
    combined_per_gene: dict[str, pd.DataFrame] = {}
    coverage_per_gene: dict[str, pd.Series] = {}

    for gene in genes:
        ensg = gene["ensembl_id"]

        # 1. Expression ensemble (only selected RNA sources)
        rna_sources = [s for s in (sources or ["depmap", "hpa", "geo"]) if s != "protein"]
        expr_rrf, coverage = rank_expression(ensg, scoring_method, enabled_sources=rna_sources)
        coverage_per_gene[gene["hugo"]] = coverage

        # 2. Protein (always scored, independent of the RNA source filter)
        prot_rrf = rank_protein(ensg)

        # 3. Combine
        combined = combine_rna_protein(expr_rrf, prot_rrf, w_rna, w_protein)

        # 4. Mutation/Fusion filter
        combined = apply_mutation_filter(combined, mutation_mode, ensg)
        combined = apply_fusion_filter(combined, fusion_mode, gene["hugo"])
        combined = apply_instability_filter(combined, msi_max, cin_max)
        combined = apply_metabolite_filter(combined, exclude_metabolite, metabolite_threshold)
        combined = apply_mirna_filter(combined, exclude_mirna, mirna_threshold)

        combined_per_gene[gene["hugo"]] = combined

    # 5. Multi-gene combination
    if len(genes) == 1:
        gene = genes[0]
        final_df = combined_per_gene[gene["hugo"]].copy()
        ascending = gene["direction"] == "low"
        final_df = final_df.sort_values("combined_score", ascending=ascending).reset_index(drop=True)
        final_df["final_rank"] = range(1, len(final_df) + 1)
        final_df["final_score"] = final_df["combined_score"]
    else:
        gene_ranks: dict[str, pd.Series] = {}
        for gene in genes:
            df_g = combined_per_gene[gene["hugo"]].copy()
            ascending = gene["direction"] == "low"
            df_g = df_g.sort_values("combined_score", ascending=ascending).reset_index(drop=True)
            df_g["gene_rank"] = range(1, len(df_g) + 1)
            gene_ranks[gene["hugo"]] = df_g.set_index("ach_id")["gene_rank"]

        # Multi-gene fusion keeps raw-sum RRF (a cell line strong across MORE
        # genes should rank higher — that is the intended behaviour here).
        multi_rrf = _rrf(gene_ranks, average=False)

        rows = []
        for ach in multi_rrf.index:
            confidences = []
            scenarios = []
            for gene in genes:
                gdf = combined_per_gene[gene["hugo"]]
                match = gdf[gdf["ach_id"] == ach]
                if len(match) > 0:
                    confidences.append(match["coverage_confidence"].iloc[0])
                    scenarios.append(match["scenario"].iloc[0])

            rows.append({
                "ach_id": ach,
                "final_score": float(multi_rrf[ach]),
                "coverage_confidence": float(np.mean(confidences)) if confidences else 0.0,
                "scenario": " | ".join(scenarios),
            })

        final_df = pd.DataFrame(rows)
        final_df = final_df.sort_values("final_score", ascending=False).reset_index(drop=True)
        final_df["final_rank"] = range(1, len(final_df) + 1)

    if final_df.empty:
        return []

    # 6. Merge metadata
    ach_ids = final_df["ach_id"].tolist()
    meta = data_service.get_cell_lines_metadata(ach_ids)

    # 7. Apply post-filters
    results = []
    for _, row in final_df.iterrows():
        cl = meta.get(row["ach_id"], {})

        # Disease filter
        if disease_filter and (cl.get("primary_disease") or "").lower() != disease_filter.lower():
            continue

        # Lineage filter
        if lineage_filter and (cl.get("lineage") or "").lower() != lineage_filter.lower():
            continue

        # Core only: require data in all 3 expression sources (for first gene)
        is_core = False
        first_hugo = genes[0]["hugo"]
        if first_hugo in coverage_per_gene:
            cov = coverage_per_gene[first_hugo]
            is_core = row["ach_id"] in cov.index and cov[row["ach_id"]] >= 3

        if core_only and not is_core:
            continue

        # Collect mutations for include mode
        mutations = None
        if mutation_mode == "include":
            all_muts = []
            for gene in genes:
                gene_muts = data_service.get_mutations_for_gene(gene["ensembl_id"])
                all_muts.extend([m for m in gene_muts if m["ach_id"] == row["ach_id"]])
            mutations = all_muts if all_muts else None

        # Collect fusions for include mode
        fusions = None
        if fusion_mode == "include":
            all_fusions = []
            for gene in genes:
                gene_fusions = data_service.get_fusions_for_gene(gene["hugo"])
                all_fusions.extend([f for f in gene_fusions if f["ach_id"] == row["ach_id"]])
            fusions = all_fusions if all_fusions else None

        score_col = "final_score" if "final_score" in row.index else "combined_score"
        results.append({
            "ach_id": row["ach_id"],
            "cell_line_name": cl.get("cell_line_name"),
            "primary_disease": cl.get("primary_disease"),
            "lineage": cl.get("lineage"),
            "growth_pattern": cl.get("growth_pattern"),
            "score": round(float(row[score_col]), 4),
            "confidence": round(float(row["coverage_confidence"]), 2),
            "scenario": row.get("scenario", ""),
            "is_core": is_core,
            "mutations": mutations,
            "fusions": fusions,
        })

    # Re-rank after filters
    results.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    results = results[:top_n]

    # Q7 assay compatibility warnings (does NOT change ranking order)
    if assay_type and assay_type != "none":
        from app.services.q7_warning_checker import check_q7_warnings

        dim = pd.DataFrame(results)[["ach_id", "cell_line_name", "lineage", "growth_pattern"]]
        q7 = check_q7_warnings(dim, assay_type)
        q7_map = q7.set_index("ach_id")[["q7_status", "q7_warning"]].to_dict("index")
        for r in results:
            info = q7_map.get(r["ach_id"], {})
            r["q7_status"] = info.get("q7_status", "OK")
            r["q7_warning"] = info.get("q7_warning", "")

    return results