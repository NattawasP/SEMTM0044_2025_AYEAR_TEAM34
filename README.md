# CellLineFinder — non-gene expression, exclusion and similarity

Work on the contextual data layers (metabolomics, microRNA, genomic
signatures), the exclusion criteria, and the cell line similarity component.

## Layout

- `src/pipeline.py` — packaged pipeline: load tables, build the feature
  matrix, rank for a target gene with exclusion criteria applied.
- `tests/test_pipeline.py` — tests for the above.
- `app.py` — standalone demo front end.
- `notebooks/Victor_Data Exploration/` — see below.

## Notebooks, in run order

1. `Rough.ipynb` — cleans the three contextual layers into long format and
   recovers cell line identifiers missing from DepMap metadata via
   Cellosaurus cross-references. Writes the `*_clean.parquet` files the
   others depend on, so run it first.
2. `Convert_To_Parquet.ipynb` — reshapes those layers and writes the CSVs
   the harmonisation step consumes.
3. `Percentile_Ranking.ipynb` — builds the composite ranking baselines for
   EGFR and ERBB2.
4. `Exclusion_and_Similarity.ipynb` — validates the exclusion filters
   against their source tables and prototypes the similarity component.
5. `Similarity_Comparison.ipynb` — evaluates similarity across all 1,412
   cell lines with a recorded lineage. Produces `lineage_separation.png`,
   which is Figure B.1 in the report.
6. `Pipeline_demo.ipynb` — end-to-end run of `src/pipeline.py`.

Independent of the above: `File Details.ipynb` (survey of all fourteen raw
sources) and `Fusion_Deduplication.ipynb` (fusion table dedupe, 43,095 rows
to 34,121). `API_Validation.ipynb` needs the backend running on
`localhost:8000`.

All random sampling is seeded, so the reported figures reproduce exactly.
