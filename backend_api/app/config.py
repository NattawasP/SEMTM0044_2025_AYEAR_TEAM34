"""
Application configuration.
Reads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env file if present


# ── Data directory ────────────────────────────────────────────
# Points to the folder containing Parquet files produced by csv_to_parquet.py
DATA_DIR = Path(os.getenv(
    "CLF_DATA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "data_prepare" / "data"),
))

# ── Parquet file paths ────────────────────────────────────────
PARQUET = {
    "dim_cell_lines":       DATA_DIR / "dim_cell_lines.parquet",
    "dim_genes":            DATA_DIR / "dim_genes.parquet",
    "fact_expression_depmap": DATA_DIR / "fact_expression_depmap.parquet",
    "fact_expression_hpa":  DATA_DIR / "fact_expression_hpa.parquet",
    "fact_expression_geo":  DATA_DIR / "fact_expression_geo.parquet",
    "fact_proteomics":      DATA_DIR / "fact_proteomics.parquet",
    "fact_mutations":       DATA_DIR / "fact_mutations.parquet",
    "fact_fusions":         DATA_DIR / "fact_fusions.parquet",
}

# ── Ranking defaults ─────────────────────────────────────────
DEFAULT_W_RNA = 0.7
DEFAULT_W_PROTEIN = 0.3
DEFAULT_TOP_N = 20
RRF_K = 60

# ── Server ───────────────────────────────────────────────────
API_HOST = os.getenv("CLF_HOST", "0.0.0.0")
API_PORT = int(os.getenv("CLF_PORT", "8000"))
CORS_ORIGINS = os.getenv("CLF_CORS_ORIGINS", "*").split(",")
