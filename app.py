import sys, os
import streamlit as st
sys.path.append(os.path.dirname(__file__))

from src.pipeline import (load_tables, build_feature_matrix, rank_cell_lines,
                          apply_full_exclusion, recommend_similar)

st.set_page_config(page_title="CellLineFinder", layout="wide")

@st.cache_resource
def get_data():
    tables = load_tables("data/parquet", "processed")
    master, feat_cols = build_feature_matrix(tables)
    return tables, master, feat_cols

tables, master, feat_cols = get_data()

st.sidebar.header("Search query")
gene = st.sidebar.text_input("Target gene (Ensembl ID)", "ENSG00000146648")
rna_weight = st.sidebar.slider("RNA weight", 0.0, 1.0, 0.5, 0.05)
penalty = st.sidebar.slider("Missing-protein penalty", 0.0, 1.0, 0.75, 0.05)

st.sidebar.header("Exclusion criteria")
criteria = {}
if st.sidebar.checkbox("Exclude MSI-high"):
    criteria["msi_max"] = st.sidebar.number_input("MSI threshold", value=3.0)
if st.sidebar.checkbox("Exclude high CIN"):
    criteria["cin_max"] = st.sidebar.number_input("CIN threshold", value=0.5)

mut_gene = st.sidebar.text_input("Exclude damaging mutation in (Ensembl ID)", "")
if mut_gene:
    criteria["damaging_mutation"] = mut_gene

fus_gene = st.sidebar.text_input("Exclude fusions involving (Ensembl ID)", "")
if fus_gene:
    criteria["gene_in_fusion"] = fus_gene

top_n = st.sidebar.slider("Show top", 5, 50, 20)

if st.sidebar.button("Find cell lines", type="primary"):
    ranked = rank_cell_lines(gene, tables, penalty=penalty, rna_weight=rna_weight)
    viable = apply_full_exclusion(ranked, tables, criteria=criteria)

    st.subheader(f"Results — {len(viable)} cell lines")
    cols = ["cell_line_name", "primary_disease", "lineage",
            "depmap_percentile", "hpa_percentile", "geo_percentile",
            "protein_percentile", "evidence_score", "n_sources",
            "confidence_score", "weighted_score", "has_mutation_data"]
    st.dataframe(viable[cols].head(top_n).round(2), width="stretch")

    top_pick = viable.iloc[0]["ACH_ID"]
    st.subheader(f"Alternatives to {viable.iloc[0]['cell_line_name']}")
    alts = recommend_similar(top_pick, viable, master, feat_cols)
    st.dataframe(alts.round(3) if hasattr(alts, "round") else alts, width="stretch")