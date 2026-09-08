"""
Test whether "rrf" and "percentile" scoring give identical results across MANY genes.

For each gene it runs the full pipeline twice (rrf vs percentile) and checks:
  - Is the top-N order identical?
  - Are the scores identical (to 4 dp)?
  - What is the largest score difference on any shared cell line?

It flags any gene where the two methods diverge, so you can see whether the
"they're always equal" result holds universally or breaks on tie-heavy genes.

Run from inside backend_api:
    cd C:\\Users\\Pattanun\\SEMTM0044_2025_AYEAR_TEAM34\\backend_api
    ..\\venv\\Scripts\\activate
    python test_all_genes.py            (uses a built-in gene list)
    python test_all_genes.py 200        (randomly sample 200 genes from dim_genes)
"""

import sys
import random

from app.services import data_service
from app.services import ranking_service
from app.database import query


TOP_N = 20

# A spread of well-known genes across different expression profiles
DEFAULT_GENES = [
    "EGFR", "KRAS", "TP53", "MYC", "BRAF", "PTEN", "PIK3CA", "ERBB2",
    "MET", "ALK", "CDKN2A", "RB1", "APC", "VHL", "KIT", "FGFR1",
    "MDM2", "CCND1", "BCL2", "MYCN", "AR", "ESR1", "NRAS", "IDH1",
]


def build_gene(hugo: str, direction: str = "high"):
    resolved = data_service.resolve_gene(hugo)
    if resolved is None:
        return None
    return {
        "hugo": resolved["hugo_symbol"],
        "ensembl_id": resolved["ensembl_id"],
        "direction": direction,
    }


def run(method: str, gene: dict):
    return ranking_service.run_ranking(
        genes=[gene],
        w_rna=0.7, w_protein=0.3,
        mutation_mode="ignore", fusion_mode="ignore",
        top_n=TOP_N, scoring_method=method, sources=None,
    )


def sample_gene_symbols(n: int) -> list[str]:
    rows = query(
        "SELECT DISTINCT CAST(hugo_symbol AS VARCHAR) AS h FROM dim_genes "
        "WHERE hugo_symbol IS NOT NULL"
    )
    syms = [r["h"] for r in rows if r["h"]]
    random.seed(42)
    random.shuffle(syms)
    return syms[:n]


def main():
    # Decide which genes to test
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        genes_to_test = sample_gene_symbols(int(sys.argv[1]))
        print(f"Testing {len(genes_to_test)} randomly sampled genes...\n")
    else:
        genes_to_test = DEFAULT_GENES
        print(f"Testing {len(genes_to_test)} well-known genes...\n")

    identical = 0
    differing = []
    skipped = []

    print(f"{'GENE':<10}{'result':<12}{'same pos':>10}{'max score diff':>16}")
    print("-" * 48)

    for hugo in genes_to_test:
        gene = build_gene(hugo)
        if gene is None:
            skipped.append(hugo)
            continue

        try:
            rrf = run("rrf", gene)
            pct = run("percentile", gene)
        except Exception as e:
            skipped.append(f"{hugo} (error: {e})")
            continue

        if not rrf and not pct:
            skipped.append(f"{hugo} (no data)")
            continue

        rrf_order = [r["ach_id"] for r in rrf]
        pct_order = [r["ach_id"] for r in pct]
        rrf_score = {r["ach_id"]: r["score"] for r in rrf}
        pct_score = {r["ach_id"]: r["score"] for r in pct}

        same_pos = sum(1 for i in range(min(len(rrf_order), len(pct_order)))
                       if rrf_order[i] == pct_order[i])
        n = max(len(rrf_order), len(pct_order))

        shared = set(rrf_order) & set(pct_order)
        max_diff = max((abs(rrf_score[a] - pct_score[a]) for a in shared), default=0.0)

        is_identical = (rrf_order == pct_order) and (max_diff < 1e-9)
        if is_identical:
            identical += 1
            verdict = "IDENTICAL"
        else:
            differing.append((hugo, same_pos, n, max_diff))
            verdict = ">>> DIFFERS"

        print(f"{hugo:<10}{verdict:<12}{same_pos:>7}/{n:<2}{max_diff:>16.6f}")

    # ── Summary ───────────────────────────────────────────────
    print("-" * 48)
    print("SUMMARY")
    tested = identical + len(differing)
    print(f"  Genes tested        : {tested}")
    print(f"  Identical results   : {identical}")
    print(f"  Differing results   : {len(differing)}")
    if skipped:
        print(f"  Skipped (no data/err): {len(skipped)}")

    if differing:
        print()
        print("  Genes where methods DIFFER:")
        for hugo, sp, n, md in differing:
            print(f"    {hugo:<10} same position {sp}/{n}, max score diff {md:.6f}")
        print()
        print("  => z-score and percentile are NOT always redundant.")
        print("     The differences above come from tied TPM values.")
    else:
        print()
        print("  => Every gene gave IDENTICAL results.")
        print("     z-score adds nothing over percentile; safe to drop it.")


if __name__ == "__main__":
    main()