"""
CellLineFinder pipeline: rank cell lines for a target gene, apply exclusion
criteria, and find similar alternatives.

Expression tables are read lazily per gene from parquet rather than loaded
into memory, since a single query only needs ~1,500 of ~170M rows.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity


def load_tables(parquet_dir, processed_dir):
    """
    Load the small tables into memory. The large expression tables stay on
    disk and are filtered per gene at query time.
    """
    return {
        "_dir":         parquet_dir,
        "mutations":    pd.read_parquet(f"{parquet_dir}/fact_mutations.parquet"),
        "fusions":      pd.read_parquet(f"{parquet_dir}/fact_fusions.parquet"),
        "dim":          pd.read_parquet(f"{parquet_dir}/dim_cell_lines.parquet"),
        "signatures":   pd.read_parquet(f"{processed_dir}/signatures_clean.parquet"),
        "metabolomics": pd.read_parquet(f"{processed_dir}/metabolomics_clean.parquet"),
        "mirna":        pd.read_parquet(f"{processed_dir}/mirna_clean.parquet"),
    }


def _read_gene(parquet_dir, fname, ensembl_id, cols):
    """Read only the rows for one gene, using parquet predicate pushdown."""
    return pd.read_parquet(f"{parquet_dir}/{fname}.parquet",
                           columns=cols,
                           filters=[("ensembl_id", "==", ensembl_id)])


def rank_cell_lines(ensembl_id, tables, penalty=0.75, rna_weight=0.5,
                    value_col="log2_tpm_plus1"):
    """Rank cell lines for a target gene, pairing each RNA source with proteomics."""
    pdir = tables["_dir"]

    def aggregate_source(fname, name, how="median"):
        sub = _read_gene(pdir, fname, ensembl_id, ["ACH_ID", "ensembl_id", value_col])
        agg = (sub.groupby("ACH_ID")[value_col]
                  .agg(value=how, spread="std", n_reps="count")
                  .reset_index())
        agg["spread"] = agg["spread"].fillna(0)
        agg["percentile"] = agg["value"].rank(pct=True) * 100
        return agg.rename(columns={
            "value":      f"{name}_value",
            "spread":     f"{name}_spread",
            "n_reps":     f"{name}_n_reps",
            "percentile": f"{name}_percentile",
        })

    rna = (aggregate_source("fact_expression_depmap", "depmap")
           .merge(aggregate_source("fact_expression_hpa", "hpa"), on="ACH_ID", how="outer")
           .merge(aggregate_source("geo", "geo"), on="ACH_ID", how="outer"))

    prot = _read_gene(pdir, "fact_proteomics", ensembl_id,
                      ["ACH_ID", "ensembl_id", "protein_intensity", "is_detected"])
    prot = prot.drop(columns="ensembl_id").dropna(subset=["protein_intensity"])
    prot["protein_percentile"] = prot["protein_intensity"].rank(pct=True) * 100

    df = rna.merge(prot, on="ACH_ID", how="left")

    for source in ["depmap", "hpa", "geo"]:
        rna_pct  = df[f"{source}_percentile"]
        prot_pct = df["protein_percentile"]
        has_rna  = rna_pct.notna()
        has_prot = prot_pct.notna()

        strength  = np.where(has_prot,
                             rna_weight * rna_pct + (1 - rna_weight) * prot_pct,
                             rna_pct)
        gap       = (rna_pct - prot_pct).abs() / 100
        agreement = np.where(has_prot, 1 / (1 + gap), 1.0)
        coverage  = np.where(has_prot, 1.0, penalty)

        df[f"{source}_strength"] = pd.Series(strength, index=df.index).where(has_rna)
        df[f"{source}_conf"]     = pd.Series(coverage * agreement, index=df.index).where(has_rna)

    geo_cv = df["geo_spread"] / df["geo_value"].replace(0, np.nan)
    df["geo_conf"] = df["geo_conf"] * (1 / (1 + geo_cv.fillna(0)))

    s_cols = [f"{s}_strength" for s in ["depmap", "hpa", "geo"]]
    c_cols = [f"{s}_conf"     for s in ["depmap", "hpa", "geo"]]

    df["evidence_score"]   = df[s_cols].mean(axis=1)
    df["n_sources"]        = df[s_cols].notna().sum(axis=1)
    df["source_std"]       = df[s_cols].std(axis=1).fillna(0)
    df["confidence_score"] = ((df["n_sources"] / 3)
                              * (1 / (1 + df["source_std"] / 100))
                              * df[c_cols].mean(axis=1))
    df["weighted_score"]   = df["evidence_score"] * df["confidence_score"]

    dim = tables["dim"]
    df = df.merge(dim[["ach_id", "cell_line_name", "primary_disease", "lineage"]],
                  left_on="ACH_ID", right_on="ach_id", how="left").drop(columns="ach_id")

    return df.sort_values("weighted_score", ascending=False).reset_index(drop=True)


def apply_full_exclusion(ranked_df, tables, criteria=None):
    """Filter cell lines against user-supplied exclusion criteria."""
    criteria = criteria or {}
    merged = pd.merge(ranked_df, tables["signatures"],
                      left_on="ACH_ID", right_index=True, how="left")
    exclude_cond = pd.Series(False, index=merged.index)

    if "msi_max" in criteria:
        exclude_cond |= (merged["MSIScore"] > criteria["msi_max"]).fillna(False).astype(bool)
    if "cin_max" in criteria:
        exclude_cond |= (merged["CIN"] > criteria["cin_max"]).fillna(False).astype(bool)

    if "metabolite" in criteria:
        name, threshold = criteria["metabolite"]
        metab_df = tables.get("metabolomics")
        if metab_df is None or name not in metab_df.columns:
            raise ValueError(f"Metabolite '{name}' not found in metabolomics data.")
        if threshold is None:
            raise ValueError(f"No threshold supplied for metabolite '{name}'.")
        high = metab_df.set_index("DepMap_ID")[name] > threshold
        exclude_cond |= merged["ACH_ID"].map(high).eq(True)

    if "mirna" in criteria:
        name, threshold = criteria["mirna"]
        mirna_df = tables.get("mirna")
        if mirna_df is None or name not in mirna_df.index:
            raise ValueError(f"miRNA '{name}' not found in miRNA data.")
        if threshold is None:
            raise ValueError(f"No threshold supplied for miRNA '{name}'.")
        high = mirna_df.loc[name] > threshold
        exclude_cond |= merged["ACH_ID"].map(high).eq(True)

    if "gene_expressed" in criteria:
        gene, pct_threshold = criteria["gene_expressed"]
        sub = _read_gene(tables["_dir"], "fact_expression_depmap", gene,
                         ["ACH_ID", "ensembl_id", "log2_tpm_plus1"])
        sub = sub.groupby("ACH_ID")["log2_tpm_plus1"].median()
        high = sub.rank(pct=True) * 100 > pct_threshold
        exclude_cond |= merged["ACH_ID"].map(high).eq(True)

    if "damaging_mutation" in criteria:
        gene = criteria["damaging_mutation"]
        mut_df = tables.get("mutations")
        if mut_df is None:
            raise ValueError("Mutations table not supplied.")
        hit = mut_df[(mut_df["ensembl_id"] == gene) &
                     (mut_df["is_damaging"] | mut_df["is_lof"] | mut_df["is_hotspot"])]["ach_id"].unique()
        exclude_cond |= merged["ACH_ID"].isin(hit)

    if "gene_in_fusion" in criteria:
        gene = criteria["gene_in_fusion"]
        fus_df = tables.get("fusions")
        if fus_df is None:
            raise ValueError("Fusions table not supplied.")
        g1 = fus_df["gene1_ensg"].str.extract(r"(ENSG\d+)")[0]
        g2 = fus_df["gene2_ensg"].str.extract(r"(ENSG\d+)")[0]
        hit = fus_df.loc[(g1 == gene) | (g2 == gene), "ach_id"].unique()
        exclude_cond |= merged["ACH_ID"].isin(hit)

    if "mutations" in tables:
        merged["has_mutation_data"] = merged["ACH_ID"].isin(tables["mutations"]["ach_id"])
    if "fusions" in tables:
        merged["has_fusion_data"] = merged["ACH_ID"].isin(tables["fusions"]["ach_id"])

    viable = merged[~exclude_cond].copy()
    print(f"Original: {len(merged)} | Excluded: {exclude_cond.sum()} | Remaining: {len(viable)}")
    return viable


def build_feature_matrix(tables):
    """
    Combine the three contextual layers into one scaled per-cell-line matrix.
    Standardised so the miRNA block does not dominate the distance calculation.
    """
    sig_c   = tables["signatures"].reset_index().rename(columns={"ModelID": "ACH_ID"})
    metab_c = tables["metabolomics"].rename(columns={"DepMap_ID": "ACH_ID"}).drop(columns=["CCLE_ID"])
    mirna_c = tables["mirna"].T
    mirna_c.index.name = "ACH_ID"
    mirna_c = mirna_c.reset_index()

    master = (sig_c.merge(metab_c, on="ACH_ID", how="inner")
                   .merge(mirna_c, on="ACH_ID", how="inner"))

    feat_cols = [c for c in master.columns if c != "ACH_ID"]
    X = master[feat_cols].astype(float)
    X = X.fillna(X.median())
    master[feat_cols] = StandardScaler().fit_transform(X)

    return master, feat_cols


def recommend_similar(target_ach, viable_df, master, feat_cols, top_n=10):
    """Find the most similar viable cell lines to a target."""
    if target_ach not in master["ACH_ID"].values:
        return f"Cannot compute: {target_ach} missing from one or more omics layers."

    target_vec = master.loc[master["ACH_ID"] == target_ach, feat_cols]
    pool = viable_df[["ACH_ID", "cell_line_name", "evidence_score"]].merge(
        master, on="ACH_ID", how="inner")
    pool = pool[pool["ACH_ID"] != target_ach].copy()

    if pool.empty:
        return "No viable cell lines remaining with matching omics data."

    pool["similarity_score"] = cosine_similarity(target_vec, pool[feat_cols])[0]
    return (pool.sort_values("similarity_score", ascending=False)
                .head(top_n)[["ACH_ID", "cell_line_name", "evidence_score", "similarity_score"]])


def find_cell_lines(ensembl_id, tables, master, feat_cols, criteria=None,
                    target_ach=None, top_n=10, penalty=0.75, rna_weight=0.5):
    """Full pipeline: rank, exclude, then find alternatives to the top pick."""
    ranked = rank_cell_lines(ensembl_id, tables, penalty=penalty, rna_weight=rna_weight)
    viable = apply_full_exclusion(ranked, tables, criteria=criteria)

    if target_ach is None and len(viable):
        target_ach = viable.iloc[0]["ACH_ID"]

    alternatives = None
    if target_ach is not None:
        alternatives = recommend_similar(target_ach, viable, master, feat_cols, top_n=top_n)

    return {"ranked": ranked, "viable": viable,
            "top_pick": target_ach, "alternatives": alternatives}