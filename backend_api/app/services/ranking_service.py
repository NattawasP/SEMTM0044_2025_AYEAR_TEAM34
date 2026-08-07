"""
Core ranking algorithm.

Pipeline:
  1. Expression ranking: Z-Score + Percentile per source → RRF ensemble
  2. Protein ranking: Z-Score + Percentile → RRF
  3. Combined RNA + Protein (4 scenarios, configurable weights)
  4. Mutation/Fusion hard filter (include/exclude/ignore)
  5. Multi-gene combination via RRF
  6. Optional post-filters (disease, lineage, core-only)
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


def _rrf(rank_dict: dict[str, pd.Series], k: int = RRF_K) -> pd.Series:
    """Reciprocal Rank Fusion across multiple rank Series."""
    all_ids: set[str] = set()
    for s in rank_dict.values():
        all_ids.update(s.index)

    scores = pd.Series(0.0, index=list(all_ids))
    for ranks in rank_dict.values():
        for idx in ranks.index:
            scores[idx] += 1.0 / (k + ranks[idx])
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


def rank_expression(ensembl_id: str) -> tuple[pd.Series, pd.Series]:
    """
    Compute RRF expression ensemble for one gene.
    Returns (rrf_scores indexed by ach_id, source_coverage Series).
    """
    rank_dict: dict[str, pd.Series] = {}
    source_presence: dict[str, set[str]] = {}

    for src_name, src_table in EXPRESSION_SOURCES:
        df = data_service.get_expression_for_gene(ensembl_id, src_table)
        if len(df) < 2:
            continue

        tpm = df.set_index("ach_id")["tpm"]

        rank_dict[f"{src_name}_zscore"] = _zscore_rank(tpm)
        rank_dict[f"{src_name}_percentile"] = _percentile_rank(tpm)

        for ach in tpm.index:
            source_presence.setdefault(ach, set()).add(src_name)

    if not rank_dict:
        return pd.Series(dtype=float), pd.Series(dtype=int)

    rrf = _rrf(rank_dict)
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
    return _rrf(rank_dict)


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
        has_rna = ach in expr_norm.index and not np.isnan(expr_norm.get(ach, np.nan))
        has_prot = ach in prot_norm.index and not np.isnan(prot_norm.get(ach, np.nan))

        if has_rna and has_prot:
            score = w_rna * expr_norm[ach] + w_prot * prot_norm[ach]
            scenario = "RNA+Protein"
            confidence = 1.0
        elif has_rna:
            score = float(expr_norm[ach])
            scenario = "RNA only"
            confidence = w_rna
        elif has_prot:
            score = float(prot_norm[ach])
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
    df: pd.DataFrame, mode: str, ensembl_id: str
) -> pd.DataFrame:
    """Apply hard fusion filter: include / exclude / ignore."""
    if mode == "ignore":
        return df
    fused = data_service.get_fused_cell_lines(ensembl_id)
    if not fused:
        return df if mode == "exclude" else df.iloc[0:0]

    if mode == "include":
        return df[df["ach_id"].isin(fused)]
    else:
        return df[~df["ach_id"].isin(fused)]


# ── Full ranking pipeline ────────────────────────────────────

def run_ranking(
    genes: list[dict],       # [{"hugo": "EGFR", "direction": "high", "ensembl_id": "ENSG..."}]
    w_rna: float = 0.7,
    w_protein: float = 0.3,
    mutation_mode: str = "ignore",
    fusion_mode: str = "ignore",
    disease_filter: str | None = None,
    lineage_filter: str | None = None,
    core_only: bool = False,
    top_n: int = 20,
) -> list[dict]:
    """
    Execute the full ranking pipeline. Returns list of ranked cell line dicts.
    """
    # Per-gene scoring
    combined_per_gene: dict[str, pd.DataFrame] = {}
    coverage_per_gene: dict[str, pd.Series] = {}

    for gene in genes:
        ensg = gene["ensembl_id"]

        # 1. Expression ensemble
        expr_rrf, coverage = rank_expression(ensg)
        coverage_per_gene[gene["hugo"]] = coverage

        # 2. Protein
        prot_rrf = rank_protein(ensg)

        # 3. Combine
        combined = combine_rna_protein(expr_rrf, prot_rrf, w_rna, w_protein)

        # 4. Mutation/Fusion filter
        combined = apply_mutation_filter(combined, mutation_mode, ensg)
        combined = apply_fusion_filter(combined, fusion_mode, ensg)

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

        multi_rrf = _rrf(gene_ranks)

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
        })

    # Re-rank after filters
    results.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results[:top_n]
