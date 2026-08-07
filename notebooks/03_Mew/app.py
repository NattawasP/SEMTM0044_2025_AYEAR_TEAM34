import duckdb
import pandas as pd
import numpy as np
import streamlit as st
import base64
import os
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="CellLineFinder", layout="wide")

DEFAULT_PATH = r"C:\Users\Pattanun\OneDrive\Desktop\SEMTM0044_2025_AYEAR_TEAM34\notebooks\03_Mew"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "bristol_logo.png")

# =========================================================
# STYLE — badges + evidence cards
# =========================================================
st.markdown("""
<style>
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}

    .cl-logo-row {margin-bottom: 10px;}
    .cl-logo-row img {height: 110px !important; width: auto !important;}

    .cl-navbar {
        background-color: #0f1729;
        padding: 12px 24px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        margin-bottom: 20px;
    }
    .cl-navbar-title {font-size: 20px; font-weight: 700;}
    .cl-accent-yellow {color: #ffc107;}
    .cl-accent-white {color: #ffffff;}
    .cl-navbar-sub {font-size: 12px; color: #94a3b8 !important; margin-left: 10px;}

    .cl-badge-core {
        background-color: #dbeafe;
        color: #1d4ed8;
        font-size: 10px;
        font-weight: 700;
        padding: 1px 6px;
        border-radius: 4px;
        margin-left: 6px;
    }

    .cl-tag {
        display: inline-block;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 10px;
        margin-right: 4px;
        background-color: #f1f5f9;
        color: #334155;
    }
    .cl-tag-yes {background-color: #dcfce7; color: #15803d;}
    .cl-tag-no {background-color: #fee2e2; color: #b91c1c;}

    /* Evidence breakdown — กล่องครีมแบบใน mockup */
    .cl-evidence-card {
        background-color: #fdf6ec;
        border: 1px solid #f0e4d0;
        border-radius: 8px;
        padding: 16px 18px;
        margin-bottom: 12px;
    }
    .cl-evidence-label {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        color: #92400e !important;
        margin-bottom: 4px;
    }
    .cl-evidence-value {font-size: 14px; color: #1e293b !important;}
</style>
""", unsafe_allow_html=True)


def _logo_html():
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<div class="cl-logo-row"><img src="data:image/png;base64,{b64}"></div>'
    return ""


st.markdown("""
<div class="cl-navbar">
    <div><span class="cl-navbar-title">
        <span class="cl-accent-white">Cell</span><span class="cl-accent-yellow">Line</span><span class="cl-accent-white">Finder</span>
    </span>
    <span class="cl-navbar-sub">v1.0 · AstraZeneca x University of Bristol</span></div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# DATA LOADING (cached)
# =========================================================
@st.cache_data(show_spinner="Loading options...")
def load_options(path):
    valid_mut_genes = duckdb.sql(f"""
        SELECT DISTINCT hugo_symbol FROM '{path}/fact_mutations.parquet'
        ORDER BY hugo_symbol
    """).df()["hugo_symbol"].tolist()

    valid_fusion_genes = duckdb.sql(f"""
        SELECT gene1_hugo as gene FROM '{path}/fact_fusions.parquet'
        UNION
        SELECT gene2_hugo as gene FROM '{path}/fact_fusions.parquet'
        ORDER BY gene
    """).df()["gene"].tolist()

    lineage_options = ["all"] + duckdb.sql(f"""
        SELECT DISTINCT lineage FROM '{path}/dim_cell_lines.parquet'
        WHERE lineage IS NOT NULL ORDER BY lineage
    """).df()["lineage"].tolist()

    all_diseases = duckdb.sql(f"""
        SELECT DISTINCT primary_disease FROM '{path}/dim_cell_lines.parquet'
        WHERE primary_disease IS NOT NULL ORDER BY primary_disease
    """).df()["primary_disease"].tolist()

    metabolite_cols = [c for c in duckdb.sql(f"""
        SELECT * FROM '{path}/metabolomics_clean.parquet' LIMIT 1
    """).df().columns.tolist() if c not in ["CCLE_ID", "DepMap_ID"]]

    return valid_mut_genes, valid_fusion_genes, lineage_options, all_diseases, metabolite_cols


@st.cache_data(show_spinner=False)
def diseases_for_lineage(path, lineage):
    if lineage == "all":
        return None
    return ["all"] + duckdb.sql(f"""
        SELECT DISTINCT primary_disease FROM '{path}/dim_cell_lines.parquet'
        WHERE lineage = '{lineage}' AND primary_disease IS NOT NULL
        ORDER BY primary_disease
    """).df()["primary_disease"].tolist()


# =========================================================
# RANKING LOGIC (same as the ipywidgets version)
# =========================================================
@st.cache_data(show_spinner=False)
def run_ranking(path, target_gene, use_mutation, mutation_gene, mutation_mode, mutation_type,
                 use_fusion, fusion_gene, fusion_mode, fusion_confidence,
                 lineage_filter, disease_filter, metabolite,
                 valid_mut_genes, valid_fusion_genes, metabolite_cols):

    logs = []

    gene_exists = duckdb.sql(f"""
        SELECT COUNT(*) as n FROM '{path}/depmap.parquet'
        WHERE ensembl_id = '{target_gene}' LIMIT 1
    """).df()["n"].values[0]
    if gene_exists == 0:
        return None, None, [f"Error: '{target_gene}' not found."]

    if use_mutation and mutation_gene and mutation_gene not in valid_mut_genes:
        return None, None, [f"Error: '{mutation_gene}' not found in mutation data."]
    if use_fusion and fusion_gene and fusion_gene not in valid_fusion_genes:
        return None, None, [f"Error: '{fusion_gene}' not found in fusion data."]
    if metabolite and metabolite not in metabolite_cols:
        return None, None, [f"Error: '{metabolite}' not found in metabolomics data."]

    gene_info = duckdb.sql(f"""
        SELECT hugo_symbol, gene_type FROM '{path}/dim_genes.parquet'
        WHERE ensembl_id = '{target_gene}' LIMIT 1
    """).df()
    hugo_symbol = gene_info["hugo_symbol"].values[0] if len(gene_info) > 0 else target_gene
    gene_type = gene_info["gene_type"].values[0] if len(gene_info) > 0 else "unknown"

    logs.append(f"Running... target={target_gene} ({hugo_symbol}) | gene_type={gene_type} | "
                f"mutation={'on' if use_mutation else 'off'} | fusion={'on' if use_fusion else 'off'} | "
                f"lineage={lineage_filter} | disease={disease_filter}")

    pivot = duckdb.sql(f"""
        WITH combined AS (
            SELECT ACH_ID, CVCL_ID, ensembl_id, tpm, 'hpa' as source
            FROM '{path}/hpa.parquet' WHERE ensembl_id = '{target_gene}'
            UNION ALL
            SELECT ACH_ID, CVCL_ID, ensembl_id, tpm, 'depmap' as source
            FROM '{path}/depmap.parquet' WHERE ensembl_id = '{target_gene}'
            UNION ALL
            SELECT ACH_ID, CVCL_ID, ensembl_id, AVG(tpm) as tpm, 'geo' as source
            FROM '{path}/geo.parquet' WHERE ensembl_id = '{target_gene}'
            GROUP BY ACH_ID, CVCL_ID, ensembl_id
        ),
        with_z AS (
            SELECT *, (tpm - AVG(tpm) OVER ()) / NULLIF(STDDEV(tpm) OVER (), 0) as z_score
            FROM combined
        )
        PIVOT with_z ON source USING AVG(z_score)
        GROUP BY ACH_ID, CVCL_ID, ensembl_id
    """).df()

    pivot["RNA_z"] = pivot[["hpa", "depmap", "geo"]].mean(axis=1, skipna=True)
    pivot["n_sources"] = pivot[["hpa", "depmap", "geo"]].notna().sum(axis=1)
    pivot["source_std"] = pivot[["hpa", "depmap", "geo"]].std(axis=1, skipna=True)
    pivot["sources_available"] = pivot.apply(
        lambda row: ", ".join([s for s, col in [("HPA", "hpa"), ("DepMap", "depmap"), ("GEO", "geo")]
                                if pd.notna(row[col])]), axis=1)

    prot = duckdb.sql(f"""
        SELECT ACH_ID, protein_intensity FROM '{path}/proteomics.parquet'
        WHERE ensembl_id = '{target_gene}'
    """).df()

    df = pivot.merge(prot, on="ACH_ID", how="left")
    df_clean = df[df["ACH_ID"].notna()].copy()
    df_clean["protein_intensity_original"] = df_clean["protein_intensity"].copy()

    mut_condition = None
    if use_mutation and mutation_gene:
        mut_condition = {"damaging": "is_damaging = True", "hotspot": "is_hotspot = True",
                          "driver": "is_driver = True", "all": "1=1"}[mutation_type]
        mut_filter = duckdb.sql(f"""
            SELECT DISTINCT ach_id FROM '{path}/fact_mutations.parquet'
            WHERE hugo_symbol = '{mutation_gene}' AND {mut_condition}
        """).df()
        logs.append(f"Cell lines with {mutation_gene} ({mutation_type}): {len(mut_filter)}")
        if mutation_mode == "exclude":
            df_clean = df_clean[~df_clean["ACH_ID"].isin(mut_filter["ach_id"])].copy()
        else:
            df_clean = df_clean[df_clean["ACH_ID"].isin(mut_filter["ach_id"])].copy()

    if use_fusion and fusion_gene:
        fusion_conf_condition = "" if fusion_confidence == "all" else f"AND confidence = '{fusion_confidence}'"
        fusion_filter = duckdb.sql(f"""
            SELECT DISTINCT ach_id FROM '{path}/fact_fusions.parquet'
            WHERE (gene1_hugo = '{fusion_gene}' OR gene2_hugo = '{fusion_gene}') {fusion_conf_condition}
        """).df()
        logs.append(f"Cell lines with {fusion_gene} fusion ({fusion_confidence}): {len(fusion_filter)}")
        if fusion_mode == "exclude":
            df_clean = df_clean[~df_clean["ACH_ID"].isin(fusion_filter["ach_id"])].copy()
        else:
            df_clean = df_clean[df_clean["ACH_ID"].isin(fusion_filter["ach_id"])].copy()

    dim = duckdb.sql(f"""
        SELECT ach_id, cvcl_id, cell_line_name, primary_disease, Subtype,
               lineage, lineage_subtype, growth_pattern, primary_or_metastasis,
               sample_collection_site, sex, age
        FROM '{path}/dim_cell_lines.parquet'
    """).df()
    df_clean = df_clean.merge(dim, left_on="ACH_ID", right_on="ach_id", how="left")

    if lineage_filter != "all":
        df_clean = df_clean[df_clean["lineage"] == lineage_filter].copy()
    if disease_filter != "all":
        df_clean = df_clean[df_clean["primary_disease"] == disease_filter].copy()

    logs.append(f"Cell lines after filter: {len(df_clean)}")
    if len(df_clean) == 0:
        return None, hugo_symbol, logs + ["No cell lines found. Please adjust your criteria."]

    if metabolite:
        metab = duckdb.sql(f"""
            SELECT "DepMap_ID", "{metabolite}" as metabolite_value
            FROM '{path}/metabolomics_clean.parquet'
        """).df().rename(columns={"DepMap_ID": "ACH_ID"})
        df_clean = df_clean.merge(metab, on="ACH_ID", how="left")
        df_clean = df_clean.rename(columns={"metabolite_value": metabolite})

    if use_fusion and fusion_gene and fusion_mode == "include":
        fusion_conf_condition = "" if fusion_confidence == "all" else f"AND confidence = '{fusion_confidence}'"
        fusion_info = duckdb.sql(f"""
            SELECT ach_id, STRING_AGG(fusion_name || ' (' || confidence || ')', ', ') as fusion_events,
                   MAX(ffpm) as max_ffpm
            FROM '{path}/fact_fusions.parquet'
            WHERE (gene1_hugo = '{fusion_gene}' OR gene2_hugo = '{fusion_gene}') {fusion_conf_condition}
            GROUP BY ach_id
        """).df().rename(columns={"ach_id": "ACH_ID"})
        df_clean = df_clean.merge(fusion_info, on="ACH_ID", how="left")

    # ---- Confidence score (per-dataset approach) ----
    def normalize_col(col):
        s = df_clean[col].copy()
        s_min, s_max = s.min(), s.max()
        if s_max == s_min:
            return pd.Series(0, index=s.index)
        return (s - s_min) / (s_max - s_min)

    # per-source score = RNA only (normalize within each source)
    # if source has no data → NaN (not counted)
    df_clean["hpa_score"] = np.where(
        df_clean["hpa"].notna(),
        normalize_col("hpa"),
        np.nan
    )
    df_clean["depmap_score"] = np.where(
        df_clean["depmap"].notna(),
        normalize_col("depmap"),
        np.nan
    )
    df_clean["geo_score"] = np.where(
        df_clean["geo"].notna(),
        normalize_col("geo"),
        np.nan
    )

    # RNA confidence = sum/3 (natural coverage penalty)
    df_clean["rna_confidence"] = (
        df_clean[["hpa_score", "depmap_score", "geo_score"]]
        .sum(axis=1, skipna=True) / 3
    )

    # protein score = normalize if available, NaN if not
    protein_vals = df_clean["protein_intensity_original"]
    p_min, p_max = protein_vals.min(), protein_vals.max()
    df_clean["protein_score"] = np.where(
        protein_vals.notna(),
        (protein_vals - p_min) / (p_max - p_min),
        np.nan
    )

    # overall confidence:
    # - if protein available → RNA * 0.7 + protein * 0.3
    # - if protein missing  → RNA confidence only (no penalty)
    df_clean["confidence"] = np.where(
        df_clean["protein_score"].notna(),
        (df_clean["rna_confidence"] * 0.7) + (df_clean["protein_score"] * 0.3),
        df_clean["rna_confidence"]
    ).round(3)

    features = ["RNA_z", "protein_intensity"]
    imputer = SimpleImputer(strategy="mean")
    df_scaled = imputer.fit_transform(df_clean[features])
    scaler = StandardScaler()
    df_scaled = scaler.fit_transform(df_scaled)
    pca = PCA(n_components=1)
    df_clean["PC1"] = pca.fit_transform(df_scaled)
    df_clean["rank"] = df_clean["PC1"].rank(ascending=False).astype(int)

    loadings = "\n".join([f"  {f}: {pca.components_[0][i]:.4f}" for i, f in enumerate(features)])
    logs.append(f"PCA Loadings:\n{loadings}")

    return df_clean.sort_values("rank"), hugo_symbol, logs


# =========================================================
# SIDEBAR — filters
# =========================================================
with st.sidebar:
    st.markdown(_logo_html(), unsafe_allow_html=True)
    st.markdown("### Search Query")
    data_path = DEFAULT_PATH

    try:
        valid_mut_genes, valid_fusion_genes, lineage_options, all_diseases, metabolite_cols = load_options(data_path)
    except Exception as e:
        st.error(f"Could not load data from this path: {e}")
        st.stop()

    target_gene = st.text_input("Target gene (Ensembl ID)", value="ENSG00000146648")

    st.markdown("**— Mutation Filter —**")
    use_mutation = st.checkbox("Use mutation filter", value=False)
    mutation_gene = mutation_mode = mutation_type = None
    if use_mutation:
        mutation_gene = st.selectbox("Mutation gene", options=valid_mut_genes,
                                      index=valid_mut_genes.index("KRAS") if "KRAS" in valid_mut_genes else 0)
        mutation_mode = st.radio("Mode", ["exclude", "include"], horizontal=True)
        mutation_type = st.selectbox("Mutation type", ["damaging", "hotspot", "driver", "all"])

    st.markdown("**— Fusion Filter —**")
    use_fusion = st.checkbox("Use fusion filter", value=False)
    fusion_gene = fusion_mode = fusion_confidence = None
    if use_fusion:
        fusion_gene = st.selectbox("Fusion gene", options=[""] + valid_fusion_genes)
        fusion_mode = st.radio("Mode ", ["exclude", "include"], horizontal=True)
        fusion_confidence = st.selectbox("Confidence", ["all", "high", "medium", "low"], index=1)

    st.markdown("**— Cell Line Filter —**")
    lineage_filter = st.selectbox("Lineage", options=lineage_options)
    disease_opts = diseases_for_lineage(data_path, lineage_filter) or (["all"] + all_diseases)
    disease_filter = st.selectbox("Disease", options=disease_opts)

    st.markdown("**— Other Options —**")
    metabolite = st.selectbox("Metabolite (optional)", options=[""] + metabolite_cols)
    top_n = st.slider("Top N", min_value=5, max_value=50, value=10, step=5)

    st.markdown("**— Show Columns —**")
    show_cvcl = st.checkbox("CVCL_ID")
    show_growth = st.checkbox("Growth pattern")
    show_metastasis = st.checkbox("Primary/Metastasis")
    show_collection = st.checkbox("Collection site")
    show_subtype = st.checkbox("Subtype details")
    show_sex_age = st.checkbox("Sex / Age")
    show_dev = st.checkbox("Show debug columns")

    run_clicked = st.button("Search Cell Lines", type="primary", use_container_width=True)

# =========================================================
# RUN + DISPLAY
# =========================================================
if run_clicked:
    with st.spinner("Running ranking..."):
        df_result, hugo_symbol, logs = run_ranking(
            data_path, target_gene, use_mutation, mutation_gene, mutation_mode, mutation_type,
            use_fusion, fusion_gene, fusion_mode, fusion_confidence,
            lineage_filter, disease_filter, metabolite,
            valid_mut_genes, valid_fusion_genes, metabolite_cols
        )
    st.session_state["df_result"] = df_result
    st.session_state["hugo_symbol"] = hugo_symbol
    st.session_state["logs"] = logs
    st.session_state["selected_row"] = None
    st.session_state["mutation_filter_desc"] = (
        f"{mutation_gene} — {mutation_type} mutations ({mutation_mode}d)" if use_mutation else None
    )
    st.session_state["fusion_filter_desc"] = (
        f"{fusion_gene} fusion — confidence: {fusion_confidence} ({fusion_mode}d)" if use_fusion else None
    )

with st.expander("Run log", expanded=False):
    for line in st.session_state.get("logs", []):
        st.text(line)

df_result = st.session_state.get("df_result")
hugo_symbol = st.session_state.get("hugo_symbol")

if df_result is not None:
    # ชื่อคอลัมน์ดิบ -> ชื่อที่ user อ่านเข้าใจ
    FRIENDLY_LABELS = {
        "rank": "Rank",
        "ACH_ID": "Cell Line ID",
        "CVCL_ID": "CVCL ID",
        "cell_line_name": "Cell Line Name",
        "primary_disease": "Disease",
        "lineage": "Lineage",
        "sources_available": "Data Sources",
        "confidence": "Confidence Score",
        "growth_pattern": "Growth Pattern",
        "primary_or_metastasis": "Primary / Metastasis",
        "sample_collection_site": "Collection Site",
        "lineage_subtype": "Lineage Subtype",
        "Subtype": "Subtype",
        "sex": "Sex",
        "age": "Age",
        "fusion_events": "Fusion Events",
        "max_ffpm": "Max FFPM",
        "RNA_z": "RNA Expression (z-score)",
        "protein_intensity_original": "Protein Level (relative)",
        "hpa_score": "HPA Score",
        "depmap_score": "DepMap Score",
        "geo_score": "GEO Score",
    }

    # คอลัมน์หลักที่ user ทั่วไปเห็น
    prod_cols = ["rank", "ACH_ID", "cell_line_name", "primary_disease", "lineage",
                 "RNA_z", "protein_intensity_original",
                 "hpa_score", "depmap_score", "geo_score",
                 "confidence"]
    if show_cvcl:
        prod_cols.insert(2, "CVCL_ID")
    if show_growth:
        prod_cols.append("growth_pattern")
    if show_metastasis:
        prod_cols.append("primary_or_metastasis")
    if show_collection:
        prod_cols.append("sample_collection_site")
    if show_subtype:
        prod_cols += ["lineage_subtype", "Subtype"]
    if show_sex_age:
        prod_cols += ["sex", "age"]
    if metabolite and metabolite in df_result.columns:
        prod_cols.append(metabolite)
    if "fusion_events" in df_result.columns:
        prod_cols += ["fusion_events", "max_ffpm"]
    # ตัวคอลัมน์ debug อื่นๆ — โชว์เฉพาะตอนติ๊ก "Show debug columns"
    if show_dev:
        prod_cols += [c for c in df_result.columns if "_mutations" in c or "_has_damaging" in c]

    show_cols = [c for c in prod_cols if c in df_result.columns]
    display_df = df_result.head(top_n)[show_cols].copy()

    # แทน None/NaN/"unknown" ด้วย "No Information" (ยกเว้นคอลัมน์ confidence ที่ต้องเป็นตัวเลขไว้ทำสี/format)
    def clean_missing(x):
        if pd.isna(x):
            return "No Information"
        if isinstance(x, str) and x.strip().lower() in ("unknown", "none"):
            return "No Information"
        if isinstance(x, float):
            return f"{x:.2f}"
        return x

    for col in display_df.columns:
        if col != "confidence":
            display_df[col] = display_df[col].apply(clean_missing)

    st.markdown(f"#### Results for **{hugo_symbol}** &nbsp;·&nbsp; {len(df_result)} cell lines found")

    column_config = {
        "confidence": st.column_config.ProgressColumn(
            FRIENDLY_LABELS["confidence"], min_value=0, max_value=1, format="%.2f"
        ),
    }
    for col in display_df.columns:
        if col in FRIENDLY_LABELS and col not in column_config:
            column_config[col] = st.column_config.Column(FRIENDLY_LABELS[col])

    event = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        column_config=column_config,
    )

    # ---- Evidence breakdown panel (one section per ticked row) ----
    selected_rows = event.selection.rows if event and event.selection else []
    if selected_rows:
        st.markdown("---")
        for i in selected_rows:
            row = display_df.iloc[i]
            st.markdown(f"### {row.get('cell_line_name', row['ACH_ID'])} — Evidence Breakdown")
            st.markdown(f"**Score: {row.get('confidence', 'n/a')}**")

            rna_val = (f"z-score = {row['RNA_z']} (relative to all cell lines)"
                       if "RNA_z" in row.index and row["RNA_z"] != "No Information"
                       else "No RNA expression data available for this cell line")

            protein_val = (f"Relative level = {row['protein_intensity_original']}"
                            if "protein_intensity_original" in row.index
                            and row["protein_intensity_original"] != "No Information"
                            else "No protein data available for this cell line")

            mut_desc = st.session_state.get("mutation_filter_desc")
            fus_desc = st.session_state.get("fusion_filter_desc")
            mut_html = f"Mutation filter: {mut_desc}" if mut_desc else "No mutation filter applied"
            if fus_desc:
                fus_events = row.get("fusion_events", "No fusion events on record for this cell line")
                mut_html += f"<br>Fusion filter: {fus_desc}<br>{fus_events}"
            else:
                mut_html += "<br>No fusion filter applied"

            lineage_disease = f"{row.get('lineage', '')} — {row.get('primary_disease', '')}"

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""
                <div class="cl-evidence-card">
                    <div class="cl-evidence-label">RNA Expression</div>
                    <div class="cl-evidence-value">{rna_val}</div>
                </div>
                <div class="cl-evidence-card">
                    <div class="cl-evidence-label">Mutations / Fusions</div>
                    <div class="cl-evidence-value">{mut_html}</div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="cl-evidence-card">
                    <div class="cl-evidence-label">Protein Detection</div>
                    <div class="cl-evidence-value">{protein_val}</div>
                </div>
                <div class="cl-evidence-card">
                    <div class="cl-evidence-label">Lineage &amp; Disease</div>
                    <div class="cl-evidence-value">{lineage_disease}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("---")
else:
    st.info("Set your filters in the sidebar and click **Search Cell Lines** to run the ranking.")
