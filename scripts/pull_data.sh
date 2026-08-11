#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# pull_data.sh — Download CellLineFinder Parquet files from
#                Google Drive to an EC2 instance.
#
# Usage:
#   chmod +x pull_data.sh
#   ./pull_data.sh              # downloads to ../data_prepare/data/
#   ./pull_data.sh /opt/clf/data  # downloads to custom directory
#
# Prerequisites:
#   pip install gdown
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# Google Drive folder ID (from shared link)
GDRIVE_FOLDER_ID="1YCoHziGufG7rd4PiCo8pT4EYcMP1nO4J"

# Target directory — default is the path the backend expects
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${1:-${SCRIPT_DIR}/../data_prepare/data}"

echo "╔════════════════════════════════════════════╗"
echo "║  CellLineFinder — Parquet Data Downloader  ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# ── 1. Check / install gdown ────────────────────────────────
if ! command -v gdown &> /dev/null; then
    echo "→ gdown not found. Installing..."
    pip install --quiet gdown
fi

# ── 2. Create target directory ──────────────────────────────
mkdir -p "$DATA_DIR"
echo "→ Download target: $DATA_DIR"
echo ""

# ── 3. Download folder from Google Drive ────────────────────
echo "→ Downloading Parquet files from Google Drive..."
gdown --folder "https://drive.google.com/drive/folders/${GDRIVE_FOLDER_ID}" \
      --output "$DATA_DIR" \
      --remaining-ok

echo ""

# ── 4. Verify expected files exist ──────────────────────────
EXPECTED_FILES=(
    "dim_cell_lines.parquet"
    "dim_genes.parquet"
    "fact_expression_depmap.parquet"
    "fact_expression_hpa.parquet"
    "fact_expression_geo.parquet"
    "fact_proteomics.parquet"
    "fact_mutations.parquet"
    "fact_fusions.parquet"
)

echo "→ Verifying files..."
MISSING=0
for f in "${EXPECTED_FILES[@]}"; do
    if [ -f "$DATA_DIR/$f" ]; then
        SIZE=$(du -h "$DATA_DIR/$f" | cut -f1)
        echo "  ✓ $f ($SIZE)"
    else
        echo "  ✗ $f — MISSING"
        MISSING=$((MISSING + 1))
    fi
done

echo ""
if [ "$MISSING" -eq 0 ]; then
    echo "✓ All 8 Parquet files downloaded successfully."
    echo ""
    echo "  To point the backend at this data directory:"
    echo "    export CLF_DATA_DIR=\"$DATA_DIR\""
    echo "    cd $(dirname "$SCRIPT_DIR") && python -m backend_api.run"
else
    echo "⚠ $MISSING file(s) missing. Check the Google Drive folder."
    exit 1
fi
