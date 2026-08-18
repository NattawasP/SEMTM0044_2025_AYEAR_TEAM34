"""
Compare the current ranking (RRF = raw SUM across RNA sources) against a
proposed ranking (RRF = AVERAGE across RNA sources, i.e. divided by the number
of sources that actually have data for each cell line).

The goal: verify that cell lines with high RNA in the sources they DO have
(but missing one source, e.g. no GEO) stop being pushed down the ranking.

This script does NOT change any project code — it re-implements both scoring
variants locally using the same data_service, and prints a side-by-side top-N.

Run from inside backend_api:
    cd C:\\Users\\Pattanun\\SEMTM0044_2025_AYEAR_TEAM34\\backend_api
    ..\\venv\\Scripts\\activate
    python compare_avg_rrf.py EGFR
"""

import sys
import numpy as np
import pandas as pd
from scipy import stats

from app.config import RRF_K
from app.services import data_service

TOP_N = 25

EXPRESSION_SOURCES = [
    ("depmap", "fact_expression_depmap"),
    ("hpa", "fact_expression_hpa"),
    ("geo", "fact_expression_geo"),
]


def zscore_rank(series):
    z = stats.zscore(series, nan_policy="omit")
    return pd.Series(z, index=series.index).rank(ascending=False, method="min")


def percentile_rank(series):
    pct = series.rank(pct=True, method="average")
    return pct.rank(ascending=False, method="min")


def norm01(s):
    if len(s) == 0:
        return s
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


def build_rna(ensg):
    """Return dict of rank Series per (source, method) and a coverage count per ach_id."""
    rank_dict = {}
    coverage = {}
    for src_name, src_table in EXPRESSION_SOURCES:
        df = data_service.get_expression_for_gene(ensg, src_table)
        if len(df) < 2:
            continue
        tpm = df.set_index("ach_id")["tpm"]
        rank_dict[f"{src_name}_z"] = zscore_rank(tpm)
        rank_dict[f"{src_name}_p"] = percentile_rank(tpm)
        for ach in tpm.index:
            coverage[ach] = coverage.get(ach, 0) + 1
    return rank_dict, pd.Series(coverage)


def rrf_sum(rank_dict):
    """Current behaviour: raw sum of 1/(k+rank) across all rank series."""
    all_ids = set()
    for s in rank_dict.values():
        all_ids.update(s.index)
    scores = pd.Series(0.0, index=list(all_ids))
    for ranks in rank_dict.values():
        for idx in ranks.index:
            scores[idx] += 1.0 / (RRF_K + ranks[idx])
    return scores


def rrf_avg(rank_dict):
    """Proposed: same sum, but divided by how many rank series covered each id."""
    all_ids = set()
    for s in rank_dict.values():
        all_ids.update(s.index)
    scores = pd.Series(0.0, index=list(all_ids))
    counts = pd.Series(0, index=list(all_ids))
    for ranks in rank_dict.values():
        for idx in ranks.index:
            scores[idx] += 1.0 / (RRF_K + ranks[idx])
            counts[idx] += 1
    return scores / counts


def build_protein(ensg):
    df = data_service.get_protein_for_gene(ensg)
    if len(df) < 2:
        return pd.Series(dtype=float)
    intensity = df.set_index("ach_id")["protein_intensity"]
    rd = {"z": zscore_rank(intensity), "p": percentile_rank(intensity)}
    all_ids = set(intensity.index)
    scores = pd.Series(0.0, index=list(all_ids))
    for ranks in rd.values():
        for idx in ranks.index:
            scores[idx] += 1.0 / (RRF_K + ranks[idx])
    return scores


def combine(expr_rrf, prot_rrf, w_rna=0.7, w_prot=0.3):
    en = norm01(expr_rrf)
    pn = norm01(prot_rrf)
    ids = set(en.index) | set(pn.index)
    rows = []
    for ach in ids:
        has_r = ach in en.index and not np.isnan(en.get(ach, np.nan))
        has_p = ach in pn.index and not np.isnan(pn.get(ach, np.nan))
        if has_r and has_p:
            s = w_rna * en[ach] + w_prot * pn[ach]
        elif has_r:
            s = w_rna * float(en[ach])
        elif has_p:
            s = w_prot * float(pn[ach])
        else:
            continue
        rows.append((ach, s))
    return pd.DataFrame(rows, columns=["ach_id", "score"]).set_index("ach_id")["score"]


def ranked_table(scores, coverage, meta, n=TOP_N):
    df = scores.sort_values(ascending=False).head(n)
    out = []
    for rank, (ach, sc) in enumerate(df.items(), 1):
        cl = meta.get(ach, {})
        name = cl.get("cell_line_name") or ach
        cov = int(coverage.get(ach, 0))  # coverage is already the number of sources (1-3)
        out.append((rank, name, ach, round(float(sc), 4), cov))
    return out


def main():
    hugo = sys.argv[1] if len(sys.argv) > 1 else "EGFR"
    g = data_service.resolve_gene(hugo)
    if not g:
        print(f"Gene {hugo} not found")
        return
    ensg = g["ensembl_id"]

    rank_dict, coverage = build_rna(ensg)
    prot = build_protein(ensg)

    sum_scores = combine(rrf_sum(rank_dict), prot)
    avg_scores = combine(rrf_avg(rank_dict), prot)

    all_ids = list(set(sum_scores.index) | set(avg_scores.index))
    meta = data_service.get_cell_lines_metadata(all_ids)

    sum_tbl = ranked_table(sum_scores, coverage, meta)
    avg_tbl = ranked_table(avg_scores, coverage, meta)

    print("=" * 92)
    print(f"{hugo}: CURRENT (sum RRF)  vs  PROPOSED (average RRF)   — top {TOP_N}")
    print("  'src' = number of RNA sources with data (1-3)")
    print("=" * 92)
    print(f"{'#':>3}  {'CURRENT (sum)':<28}{'score':>8}{'src':>4}    {'PROPOSED (avg)':<28}{'score':>8}{'src':>4}")
    print("-" * 92)
    for i in range(TOP_N):
        a = sum_tbl[i] if i < len(sum_tbl) else None
        b = avg_tbl[i] if i < len(avg_tbl) else None
        a_txt = f"{a[1]} ({a[2]})" if a else ""
        a_sc = f"{a[3]:.4f}" if a else ""
        a_src = f"{a[4]}" if a else ""
        b_txt = f"{b[1]} ({b[2]})" if b else ""
        b_sc = f"{b[3]:.4f}" if b else ""
        b_src = f"{b[4]}" if b else ""
        print(f"{i+1:>3}  {a_txt:<28}{a_sc:>8}{a_src:>4}    {b_txt:<28}{b_sc:>8}{b_src:>4}")

    # Highlight cell lines that RISE the most under averaging
    print("-" * 92)
    sum_pos = {row[2]: row[0] for row in sum_tbl}
    avg_pos = {row[2]: row[0] for row in avg_tbl}
    risers = []
    for ach, ap in avg_pos.items():
        sp = sum_pos.get(ach)
        name = meta.get(ach, {}).get("cell_line_name") or ach
        src = next((r[4] for r in avg_tbl if r[2] == ach), "?")
        if sp is None:
            risers.append((name, src, f"NEW in top{TOP_N} (was outside)", ap))
        elif sp - ap >= 3:
            risers.append((name, src, f"#{sp} -> #{ap}", ap))
    risers.sort(key=lambda x: x[3])
    if risers:
        print("Cell lines that RISE notably under averaging (likely the RNA-high, few-source ones):")
        for name, src, change, _ in risers:
            print(f"   {name:<18} {src} src   {change}")
    else:
        print("No large risers — averaging changed little for this gene.")
    print("=" * 92)


if __name__ == "__main__":
    main()
