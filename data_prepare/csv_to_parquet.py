"""
CellLineFinder — CSV to Parquet Conversion
===========================================
Converts all harmonized CSV files to Parquet format for fast DuckDB queries.

Usage:
    python csv_to_parquet.py --input <path_to_harmonized_data> [--output <output_dir>]

Example:
    python csv_to_parquet.py --input ../harmonized_data
    python csv_to_parquet.py --input D:/Prab/Bristol/Final project/prab-branch/harmonized_data

Output goes to data_prepare/data/ by default.
"""

import argparse
import time
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


# ── Files to convert ──────────────────────────────────────────
# (filename, is_large, chunk_size)
#   is_large=True  → use chunked reading + pyarrow writer
#   is_large=False → read all at once

FILES = [
    # Dimension tables (small)
    ("dim_cell_lines.csv",          False, None),
    ("dim_genes.csv",               False, None),
    # Fact tables (large expression files)
    ("fact_expression_depmap.csv",  True,  500_000),
    ("fact_expression_hpa.csv",     True,  500_000),
    ("fact_expression_geo.csv",     True,  500_000),
    # Fact tables (medium)
    ("fact_proteomics.csv",         True,  500_000),
    # Fact tables (small)
    ("fact_mutations.csv",          False, None),
    ("fact_fusions.csv",            False, None),
    # Victor's new tables
    ("fact_metabolomics.csv",       False, None),
    ("fact_mirna.csv",              False, None),
    ("fact_signatures.csv",         False, None),
    ("dim_cell_line_parents.csv",   False, None),
]

# ── Column name normalisation ─────────────────────────────────
# Expression files use ACH_ID (uppercase); normalise to ach_id
COLUMN_RENAMES = {
    "ACH_ID": "ach_id",
}

# ── Dtype optimisation ────────────────────────────────────────
# Columns that should be stored as categorical (dictionary-encoded in Parquet)
CATEGORICAL_COLUMNS = {
    "ach_id", "cvcl_id", "ensembl_id", "hugo_symbol", "source",
    "primary_disease", "lineage", "lineage_subtype", "sex",
    "growth_pattern", "primary_or_metastasis", "sample_collection_site",
    "variant_type", "variant_info", "chrom",
    "gene1_ensg", "gene2_ensg", "gene1_hugo", "gene2_hugo",
    "fusion_name", "confidence", "reading_frame",
    "uniprot_id", "metadata_source",
    "metabolite", "mirna_id", "parent_ach_id",
}

# Boolean columns stored as strings in CSV
BOOLEAN_COLUMNS = {
    "is_expressed", "is_detected", "is_driver", "is_hotspot",
    "is_damaging", "is_lof", "has_real_name", "has_full_metadata",
}


def optimise_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Optimise DataFrame dtypes for Parquet storage."""
    # Rename columns
    df = df.rename(columns=COLUMN_RENAMES)

    for col in df.columns:
        # Categorical
        if col in CATEGORICAL_COLUMNS and col in df.columns:
            df[col] = df[col].astype("category")

        # Booleans (handle string "True"/"False")
        if col in BOOLEAN_COLUMNS and col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].map({"True": True, "False": False, "true": True, "false": False})
            df[col] = df[col].astype("boolean")

    # Downcast floats where possible
    float_cols = df.select_dtypes(include=["float64"]).columns
    for col in float_cols:
        df[col] = pd.to_numeric(df[col], downcast="float")

    return df


def convert_small(csv_path: Path, parquet_path: Path) -> tuple[int, float, float]:
    """Convert a small CSV to Parquet in one shot."""
    df = pd.read_csv(csv_path, low_memory=False)
    df = optimise_dtypes(df)
    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)

    csv_mb = csv_path.stat().st_size / (1024 * 1024)
    pq_mb = parquet_path.stat().st_size / (1024 * 1024)
    return len(df), csv_mb, pq_mb


def convert_large(csv_path: Path, parquet_path: Path, chunk_size: int) -> tuple[int, float, float]:
    """Convert a large CSV to Parquet using chunked reading + PyArrow writer."""
    writer = None
    schema = None
    total_rows = 0

    for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False)):
        chunk = optimise_dtypes(chunk)

        if schema is None:
            table = pa.Table.from_pandas(chunk, preserve_index=False)
            schema = table.schema
            writer = pq.ParquetWriter(parquet_path, schema, compression="snappy")
        else:
            table = pa.Table.from_pandas(chunk, schema=schema, preserve_index=False)

        writer.write_table(table)
        total_rows += len(chunk)

        if (i + 1) % 10 == 0:
            print(f"    ... processed {total_rows:,} rows")

    if writer is not None:
        writer.close()

    csv_mb = csv_path.stat().st_size / (1024 * 1024)
    pq_mb = parquet_path.stat().st_size / (1024 * 1024)
    return total_rows, csv_mb, pq_mb


def main():
    parser = argparse.ArgumentParser(description="Convert harmonized CSVs to Parquet")
    parser.add_argument("--input", required=True, help="Path to harmonized_data directory with CSVs")
    parser.add_argument("--output", default=None, help="Output directory (default: data_prepare/data/)")
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Default output: same directory as this script / data/
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(__file__).parent / "data"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("CellLineFinder — CSV to Parquet Conversion")
    print("=" * 65)
    print(f"Input:  {input_dir.resolve()}")
    print(f"Output: {output_dir.resolve()}")
    print()

    results = []
    total_start = time.time()

    for filename, is_large, chunk_size in FILES:
        csv_path = input_dir / filename
        parquet_name = filename.replace(".csv", ".parquet")
        parquet_path = output_dir / parquet_name

        if not csv_path.exists():
            print(f"  SKIP  {filename} — not found")
            continue

        print(f"  Converting {filename}...", end="", flush=True)
        start = time.time()

        if is_large:
            rows, csv_mb, pq_mb = convert_large(csv_path, parquet_path, chunk_size)
        else:
            rows, csv_mb, pq_mb = convert_small(csv_path, parquet_path)

        elapsed = time.time() - start
        ratio = (1 - pq_mb / csv_mb) * 100 if csv_mb > 0 else 0
        results.append((filename, rows, csv_mb, pq_mb, ratio, elapsed))
        print(f" {rows:>12,} rows | {csv_mb:>8.1f} MB → {pq_mb:>8.1f} MB ({ratio:.0f}% smaller) | {elapsed:.1f}s")

    total_elapsed = time.time() - total_start

    # Summary
    print()
    print("=" * 65)
    print("SUMMARY")
    print("=" * 65)
    total_csv = sum(r[2] for r in results)
    total_pq = sum(r[3] for r in results)
    total_rows = sum(r[1] for r in results)
    print(f"  Files converted:  {len(results)}")
    print(f"  Total rows:       {total_rows:,}")
    print(f"  CSV total:        {total_csv:.1f} MB")
    print(f"  Parquet total:    {total_pq:.1f} MB")
    print(f"  Compression:      {(1 - total_pq / total_csv) * 100:.0f}% smaller")
    print(f"  Time:             {total_elapsed:.1f}s")
    print()
    print(f"Parquet files saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
