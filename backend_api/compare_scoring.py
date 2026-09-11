"""
Compare scoring methods: "rrf" (z-score + percentile ensemble) vs "percentile" only.

Run from inside the backend_api folder:
    cd C:\\Users\\Pattanun\\SEMTM0044_2025_AYEAR_TEAM34\\backend_api
    ..\\venv\\Scripts\\activate      (if not already active)
    python compare_scoring.py EGFR

You can pass any gene symbol; defaults to EGFR.
"""

import sys

from app.services import data_service
from app.services import ranking_service


def build_gene(hugo: str, direction: str = "high") -> dict:
    """Resolve a HUGO symbol to the gene dict the pipeline expects."""
    resolved = data_service.resolve_gene(hugo)
    if resolved is None:
        print(f"Gene '{hugo}' not found in dim_genes.")
        sys.exit(1)
    return {
        "hugo": resolved["hugo_symbol"],
        "ensembl_id": resolved["ensembl_id"],
        "direction": direction,
    }


def run(method: str, gene: dict, top_n: int = 20) -> list[dict]:
    """Run the full ranking pipeline with a given scoring method."""
    return ranking_service.run_ranking(
        genes=[gene],
        w_rna=0.7,
        w_protein=0.3,
        mutation_mode="ignore",
        fusion_mode="ignore",
        top_n=top_n,
        scoring_method=method,   # "rrf" vs "percentile"
        sources=None,            # all sources (depmap, hpa, geo, protein)
    )


def main():
    hugo = sys.argv[1] if len(sys.argv) > 1 else "EGFR"
    direction = sys.argv[2] if len(sys.argv) > 2 else "high"
    top_n = 20

    gene = build_gene(hugo, direction)
    print("=" * 78)
    print(f"Comparing scoring methods for {gene['hugo']} "
          f"({gene['ensembl_id']}) — direction={direction}, top {top_n}")
    print("=" * 78)

    rrf_results = run("rrf", gene, top_n)
    pct_results = run("percentile", gene, top_n)

    rrf_order = [r["ach_id"] for r in rrf_results]
    pct_order = [r["ach_id"] for r in pct_results]

    rrf_score = {r["ach_id"]: r["score"] for r in rrf_results}
    pct_score = {r["ach_id"]: r["score"] for r in pct_results}
    name_of = {r["ach_id"]: (r.get("cell_line_name") or r["ach_id"]) for r in rrf_results}
    for r in pct_results:
        name_of.setdefault(r["ach_id"], r.get("cell_line_name") or r["ach_id"])

    # ── Side-by-side table ────────────────────────────────────
    print()
    print(f"{'#':>3}  {'RRF (z+pct)':<26}{'score':>8}   {'PERCENTILE only':<26}{'score':>8}")
    print("-" * 78)
    for i in range(top_n):
        a = rrf_order[i] if i < len(rrf_order) else None
        b = pct_order[i] if i < len(pct_order) else None
        a_txt = f"{name_of.get(a, a)} ({a})" if a else ""
        b_txt = f"{name_of.get(b, b)} ({b})" if b else ""
        a_sc = f"{rrf_score.get(a, 0):.4f}" if a else ""
        b_sc = f"{pct_score.get(b, 0):.4f}" if b else ""
        marker = "" if a == b else "  <-- differs"
        print(f"{i+1:>3}  {a_txt:<26}{a_sc:>8}   {b_txt:<26}{b_sc:>8}{marker}")

    # ── Summary ───────────────────────────────────────────────
    same_position = sum(1 for i in range(min(len(rrf_order), len(pct_order)))
                        if rrf_order[i] == pct_order[i])
    same_set = set(rrf_order) & set(pct_order)

    print("-" * 78)
    print("SUMMARY")
    print(f"  Same cell line in same position : {same_position}/{top_n}")
    print(f"  Same cell lines in top {top_n} (any order): {len(same_set)}/{top_n}")
    only_rrf = [a for a in rrf_order if a not in set(pct_order)]
    only_pct = [b for b in pct_order if b not in set(rrf_order)]
    if only_rrf:
        print(f"  Only in RRF top{top_n}       : {', '.join(name_of.get(x, x) for x in only_rrf)}")
    if only_pct:
        print(f"  Only in PERCENTILE top{top_n}: {', '.join(name_of.get(x, x) for x in only_pct)}")

    # Max score difference for shared cell lines
    if same_set:
        max_diff = max(abs(rrf_score[a] - pct_score[a]) for a in same_set
                       if a in rrf_score and a in pct_score)
        print(f"  Max score difference (shared)   : {max_diff:.4f}")
    print("=" * 78)


if __name__ == "__main__":
    main()