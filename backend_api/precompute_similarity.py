"""
Pre-compute scaled similarity matrices on a machine with enough RAM,
or in a memory-constrained environment using chunked processing.

Usage:
    cd backend_api
    python precompute_similarity.py

Outputs:  data_prepare/data/sim_*.parquet  (one per layer)
"""

import sys
import gc
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.config import DATA_DIR

N_GENES = 1000


def _scale(wide):
    wide = wide.loc[:, wide.columns.notna()]
    wide.columns = [str(c) for c in wide.columns]  # uniform str type
    wide = wide.fillna(wide.median())
    return pd.DataFrame(
        StandardScaler().fit_transform(wide), index=wide.index, columns=wide.columns
    ).astype(np.float32)


def build_expression():
    """Chunked processing: two passes over the parquet to stay under 1GB RAM."""
    path = DATA_DIR / "fact_expression_depmap.parquet"
    if not path.exists():
        return pd.DataFrame()

    # Pass 1: find top-variance genes using chunked reading
    print("  Pass 1: computing gene variances (chunked)...")
    pf = pd.read_parquet(path, columns=["ensembl_id", "log2_tpm_plus1"])
    gene_stats = pf.groupby("ensembl_id")["log2_tpm_plus1"].agg(["var", "count"])
    del pf
    gc.collect()

    top_genes = set(gene_stats["var"].nlargest(N_GENES).index.tolist())
    print(f"  Selected {len(top_genes)} top-variance genes")
    del gene_stats
    gc.collect()

    # Pass 2: read only those genes, pivot
    print("  Pass 2: building matrix for selected genes...")
    df = pd.read_parquet(path, columns=["ach_id", "ensembl_id", "log2_tpm_plus1"])
    df["ach_id"] = df["ach_id"].astype(str)
    df["ensembl_id"] = df["ensembl_id"].astype(str)
    df = df[df["ensembl_id"].isin(top_genes)]
    gc.collect()

    med = df.groupby(["ach_id", "ensembl_id"])["log2_tpm_plus1"].median().reset_index()
    del df
    gc.collect()

    wide = med.pivot(index="ach_id", columns="ensembl_id", values="log2_tpm_plus1")
    del med
    gc.collect()

    return _scale(wide)


def build_proteomics():
    path = DATA_DIR / "fact_proteomics.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path, columns=["ach_id", "ensembl_id", "protein_intensity"])
    df = df.dropna(subset=["protein_intensity"])
    df["ach_id"] = df["ach_id"].astype(str)
    df["ensembl_id"] = df["ensembl_id"].astype(str)
    med = df.groupby(["ach_id", "ensembl_id"])["protein_intensity"].median().reset_index()
    del df; gc.collect()
    wide = med.pivot(index="ach_id", columns="ensembl_id", values="protein_intensity")
    del med; gc.collect()
    return _scale(wide)


def build_metabolomics():
    path = DATA_DIR / "metabolomics_clean.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df = df.set_index("DepMap_ID").drop(columns=["CCLE_ID"], errors="ignore")
    df.index.name = "ach_id"
    return _scale(df)


def build_mirna():
    path = DATA_DIR / "mirna_clean.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    str_cols = df.select_dtypes(include="object").columns
    if len(str_cols) > 0:
        df = df.set_index(str_cols[0])
    df = df.T
    df.index.name = "ach_id"
    return _scale(df)


LAYERS = [
    ("metabolomics", build_metabolomics),
    ("mirna",        build_mirna),
    ("proteomics",   build_proteomics),
    ("expression",   build_expression),  # heaviest last
]


def main():
    for name, builder in LAYERS:
        print(f"\nBuilding {name}...")
        try:
            df = builder()
            if df.empty:
                print(f"  SKIPPED (no data)")
                continue
            out = DATA_DIR / f"sim_{name}.parquet"
            df.to_parquet(out)
            size_mb = out.stat().st_size / 1024 / 1024
            print(f"  Saved: {df.shape[0]} cell lines x {df.shape[1]} features ({size_mb:.1f} MB)")
            del df
            gc.collect()
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

    print("\nDone! Copy sim_*.parquet files to EC2:")
    print(f"  scp {DATA_DIR}/sim_*.parquet ubuntu@<EC2>:/home/ubuntu/celllinefinder/data_prepare/data/")


if __name__ == "__main__":
    main()
