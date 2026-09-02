"""
Cell line similarity — find alternatives with comparable molecular profiles.

The headline score is expression-based, combined with proteomics where both cell
lines have it. Metabolomics and miRNA are reported alongside as separate figures
rather than blended in: they separate lineages far more weakly than expression
(+0.07 against +0.30 on a same-lineage vs random pair test), so averaging them
into the score degrades it. Genomic signatures were tested and dropped; six
dimensions is too few for a stable cosine similarity.

Matrices are expensive to build, so each is computed on first use and cached.
"""

import logging
import threading
import time

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

from app.config import PARQUET
from app.database import query_df

logger = logging.getLogger(__name__)

N_GENES = 2000
W_EXPR = 0.7
W_PROT = 0.3

_cache: dict[str, pd.DataFrame] = {}
_spread: dict[str, float] = {}
_lock = threading.Lock()


def _scale(wide: pd.DataFrame) -> pd.DataFrame:
    """Fill gaps with the column median, then z-score so no feature dominates."""
    wide = wide.loc[:, wide.columns.notna()]       # drop unmapped features
    wide.columns = wide.columns.astype(str)
    wide = wide.fillna(wide.median())
    return pd.DataFrame(
        StandardScaler().fit_transform(wide), index=wide.index, columns=wide.columns
    )


def _build_expression() -> pd.DataFrame:
    # variance on log values, not raw tpm - raw variance is dominated by
    # highly-expressed genes rather than genes that actually distinguish cell lines
    top_genes = query_df(f"""
        SELECT CAST(ensembl_id AS VARCHAR) AS ensembl_id
        FROM (
            SELECT ensembl_id, var_pop(v) AS variance
            FROM (
                SELECT ach_id, ensembl_id, median(log2_tpm_plus1) AS v
                FROM fact_expression_depmap
                GROUP BY ach_id, ensembl_id
            )
            GROUP BY ensembl_id
        )
        ORDER BY variance DESC
        LIMIT {N_GENES}
    """)["ensembl_id"].tolist()

    placeholders = ", ".join(["?"] * len(top_genes))
    long = query_df(f"""
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               CAST(ensembl_id AS VARCHAR) AS ensembl_id,
               median(log2_tpm_plus1) AS v
        FROM fact_expression_depmap
        WHERE CAST(ensembl_id AS VARCHAR) IN ({placeholders})
        GROUP BY ach_id, ensembl_id
    """, top_genes)

    return _scale(long.pivot(index="ach_id", columns="ensembl_id", values="v"))


def _build_proteomics() -> pd.DataFrame:
    long = query_df("""
        SELECT CAST(ach_id AS VARCHAR) AS ach_id,
               CAST(ensembl_id AS VARCHAR) AS ensembl_id,
               median(protein_intensity) AS v
        FROM fact_proteomics
        WHERE protein_intensity IS NOT NULL
        GROUP BY ach_id, ensembl_id
    """)
    return _scale(long.pivot(index="ach_id", columns="ensembl_id", values="v"))


def _build_metabolomics() -> pd.DataFrame:
    # Wide format: rows = cell lines, cols = CCLE_ID + DepMap_ID + 225 metabolites
    # Read directly with pandas to avoid DuckDB alias issues
    path = PARQUET.get("fact_metabolomics")
    if path is None or not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df = df.set_index("DepMap_ID").drop(columns=["CCLE_ID"], errors="ignore")
    df.index.name = "ach_id"
    return _scale(df)


def _build_mirna() -> pd.DataFrame:
    # Rows = miRNAs (734), cols = ACH IDs (952) + a miRNA name column
    # Need to set miRNA name column as index before transposing
    path = PARQUET.get("fact_mirna")
    if path is None or not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    # Find the string column that holds miRNA names and use it as index
    str_cols = df.select_dtypes(include="object").columns
    if len(str_cols) > 0:
        df = df.set_index(str_cols[0])
    df = df.T  # Now rows = cell lines (ACH IDs), cols = miRNA names
    df.index.name = "ach_id"
    return _scale(df)


def _build_signatures() -> pd.DataFrame:
    # Wide format: rows = cell lines (index=ModelID), cols = 6 signature features
    path = PARQUET.get("fact_signatures")
    if path is None or not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    # Index is already ModelID from parquet
    df.index.name = "ach_id"
    return _scale(df)


BUILDERS = {
    "expression":   _build_expression,
    "proteomics":   _build_proteomics,
    "metabolomics": _build_metabolomics,
    "mirna":        _build_mirna,
    "signatures":   _build_signatures,
}


def get_layer(name: str) -> pd.DataFrame:
    """Return a scaled feature matrix, building it on first use."""
    if name in _cache:
        return _cache[name]
    with _lock:
        if name not in _cache:
            logger.info("Building %s matrix (first call — this may take a minute)...", name)
            t0 = time.time()
            _cache[name] = BUILDERS[name]()
            logger.info("Built %s matrix: %d cell lines × %d features in %.1fs",
                        name, _cache[name].shape[0], _cache[name].shape[1], time.time() - t0)
    return _cache[name]


def _similarity_against(name: str, target: str, candidates: list[str]) -> dict[str, float]:
    """Cosine similarity from target to each candidate within one layer."""
    m = get_layer(name)
    if target not in m.index:
        return {}
    pool = m.loc[m.index.intersection(candidates)]
    pool = pool[pool.index != target]
    if pool.empty:
        return {}
    sims = cosine_similarity(m.loc[[target]], pool)[0]

    if name not in _spread and len(sims) > 1:
        _spread[name] = float(np.std(sims))

    return dict(zip(pool.index, sims))



def _get_roots() -> dict[str, str]:
    """
    Map each derivative cell line to the root it descends from. Relationships
    chain (A375 SKIN CJ3 derives from CJ1, which derives from A375), so follow
    each link to the top.
    """
    global _roots
    if _roots is not None:
        return _roots

    with _lock:
        if _roots is None:
            rel = query_df("""
                SELECT CAST(ach_id AS VARCHAR) AS ach_id,
                       CAST(parent_ach_id AS VARCHAR) AS parent_ach_id
                FROM dim_cell_line_parents
            """)
            parent = dict(zip(rel["ach_id"], rel["parent_ach_id"]))

            roots = {}
            for child in parent:
                seen, node = set(), child
                while node in parent and node not in seen:
                    seen.add(node)
                    node = parent[node]
                roots[child] = node
            _roots = roots

    return _roots


def _related(a: str, b: str) -> bool:
    """True if two cell lines share a lineage of derivation in either direction."""
    roots = _get_roots()
    ra, rb = roots.get(a, a), roots.get(b, b)
    return ra == rb


def find_similar(ach_id: str, top_n: int = 10,
                 restrict_to: list[str] | None = None) -> list[dict] | None:
    """
    Cell lines with the most similar molecular profile to the target.

    Score is expression, combined with proteomics where both cell lines have it.
    The remaining layers are reported per result but do not affect the score.
    """
    expr = get_layer("expression")
    if ach_id not in expr.index:
        return None

    candidates = list(expr.index)
    if restrict_to:
        candidates = [c for c in candidates if c in set(restrict_to)]

    expr_sims = _similarity_against("expression", ach_id, candidates)
    if not expr_sims:
        return []

    prot_sims = _similarity_against("proteomics", ach_id, list(expr_sims))
    # signatures is only six dimensions, so its cosine similarity swings between
    # -0.8 and +1.0 with an sd of 0.64 against expression's 0.18 - too volatile to
    # report as a similarity figure, though it still drives the MSI/CIN exclusion
    context = {name: _similarity_against(name, ach_id, list(expr_sims))
               for name in ("metabolomics", "mirna")}

    results = []
    for other, e in expr_sims.items():
        p = prot_sims.get(other)

        # renormalise over the layers this pair actually shares, so a pair with
        # expression alone is not penalised in the score
        if p is not None:
            ratio = _spread.get("expression", 1.0) / _spread.get("proteomics", 1.0)
            score = (W_EXPR * e + W_PROT * p * ratio) / (W_EXPR + W_PROT)
            layers = ["expression", "proteomics"]
        else:
            score = e
            layers = ["expression"]

        row = {
            "ach_id": other,
            "similarity": round(float(score), 4),
            "expression_similarity": round(float(e), 4),
            "protein_similarity": round(float(p), 4) if p is not None else None,
            "scored_on": layers,
            "is_derivative": _related(ach_id, other),
        }
        for name, sims in context.items():
            v = sims.get(other)
            row[f"{name}_similarity"] = round(float(v), 4) if v is not None else None

        results.append(row)

    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:top_n]

_roots: dict[str, str] | None = None
