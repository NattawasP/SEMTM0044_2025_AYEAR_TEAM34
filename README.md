# CellLineFinder

A multi-omics ranking platform for cancer cell line selection, developed as part of an MSc dissertation project at the University of Bristol in collaboration with AstraZeneca.

Researchers specify target genes with desired expression directions, and the system ranks ~2,200 DepMap cell lines by integrating RNA expression (DepMap, HPA, GEO), proteomics, mutation/fusion annotations, metabolomics, and miRNA data through a Reciprocal Rank Fusion (RRF) ensemble scoring method.

**Live site:** [https://celllinefinder.com](https://celllinefinder.com)

---

## Features

- **Multi-gene search** with per-gene high/low expression direction toggles
- **RRF ensemble ranking** combining z-score and percentile ranks across three RNA sources and proteomics
- **Flexible filtering** — hard-filter or soft-boost by disease/lineage/subtype, mutation/fusion include/exclude, MSI/CIN instability thresholds, metabolite and miRNA exclusion
- **Assay compatibility warnings** (Q7) for adherent screens, 3D spheroids, and suspension assays
- **Cosine similarity** — find the five most similar cell lines by expression profile
- **Side-by-side comparison** of selected cell lines across all data sources
- **CSV export** of ranked results with full query metadata
- **LLM-powered chatbot** (GPT-4o-mini) for in-app data questions
- **In-app documentation** covering usage, data sources, methodology, and project information

---

## Project Structure

```
celllinefinder/
├── backend_api/               # FastAPI backend
│   ├── app/
│   │   ├── main.py            # App assembly, CORS, router registration
│   │   ├── config.py          # Environment config, Parquet paths, defaults
│   │   ├── database.py        # DuckDB connection manager (in-memory, Parquet views)
│   │   ├── models.py          # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── genes.py       # /api/genes — autocomplete, symbol resolution
│   │   │   ├── ranking.py     # /api/rank — main ranking endpoint
│   │   │   ├── celllines.py   # /api/celllines — detail, similarity, compare
│   │   │   ├── filters.py     # /api/filters — disease/lineage/subtype values
│   │   │   └── chat.py        # /api/chat — LLM chatbot endpoint
│   │   └── services/
│   │       ├── ranking_service.py     # RRF scoring, z-score, percentile logic
│   │       ├── data_service.py        # SQL queries via DuckDB
│   │       ├── similarity_service.py  # Cosine similarity across expression profiles
│   │       ├── q6_lineage_scorer.py   # Tissue-match soft boost scoring
│   │       ├── q7_assay_profiles.py   # Assay compatibility profiles
│   │       ├── q7_warning_checker.py  # Assay compatibility warning logic
│   │       ├── chat_service.py        # OpenAI function-calling loop
│   │       └── chat_tools.py          # Tool definitions for chatbot
│   └── .env                   # Environment variables (API keys — not committed)
├── frontend/                  # React + Vite SPA
│   ├── src/
│   │   ├── App.jsx            # Root component, state management, search logic
│   │   ├── api.js             # API client (fetch wrappers)
│   │   ├── exportCsv.js       # Client-side CSV export utility
│   │   └── components/
│   │       ├── SearchBar/     # Gene autocomplete with high/low toggles
│   │       ├── FilterPanel/   # Cascading filters, advanced options
│   │       ├── ResultsTable/  # Ranked results with adaptive columns
│   │       ├── DetailPanel/   # Slide-in per-cell-line evidence breakdown
│   │       ├── CompareView/   # Side-by-side comparison modal
│   │       ├── ChatWidget/    # LLM chatbot floating widget
│   │       └── DocsModal/     # In-app documentation (4 tabs)
│   └── dist/                  # Production build output
├── data_prepare/              # Data pipeline
│   ├── csv_to_parquet.py      # CSV → Parquet conversion with chunked writing
│   └── data/                  # Parquet files (not committed — see Data Setup)
├── report/                    # Dissertation LaTeX source and class files
├── harmonized_data/           # Intermediate harmonized CSVs (not committed)
├── notebooks/                 # Jupyter notebooks for data exploration
├── scripts/
│   └── pull_data.sh           # Download Parquet files from Google Drive
├── docs/
│   └── deploy_ec2.md          # EC2 deployment guide
├── .github/workflows/
│   └── deploy.yml             # GitHub Actions CI/CD pipeline
├── requirements.txt           # Python dependencies
├── start_backend.bat          # Windows: start backend with venv
└── start_frontend.bat         # Windows: start frontend dev server
```

---

## Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- **npm** 9+

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/NattawasP/SEMTM0044_2025_AYEAR_TEAM34.git
cd SEMTM0044_2025_AYEAR_TEAM34
```

### 2. Download the data

The Parquet data files are hosted on Google Drive (not committed to git due to size). Use the provided script:

```bash
pip install gdown
chmod +x scripts/pull_data.sh
./pull_data.sh
```

This downloads all Parquet files to `data_prepare/data/`. The backend reads from this directory by default.

Alternatively, if you have the harmonized CSVs in `harmonized_data/`, you can regenerate the Parquet files:

```bash
python data_prepare/csv_to_parquet.py --input harmonized_data
```

### 3. Backend setup

```bash
cd backend_api
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r ../requirements.txt
```

Create a `.env` file in `backend_api/`:

```env
OPENAI_API_KEY=your-openai-api-key   # Required for the chatbot feature
# CLF_DATA_DIR=/custom/path          # Optional: override default data directory
# CLF_PORT=8000                      # Optional: override default port
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Verify with `GET /health`.

### 4. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and proxies API requests to port 8000.

On **Windows**, you can also use the batch scripts from the repo root:

```bash
start_backend.bat    # activates venv, installs deps, runs uvicorn
start_frontend.bat   # installs deps if needed, runs vite dev server
```

---

## Data Pipeline

The pipeline transforms 14 raw datasets into query-ready Parquet files in three stages:

1. **Harmonization** — Python scripts and Jupyter notebooks clean each dataset: cell line names are resolved to DepMap accessions, gene symbols to Ensembl IDs, expression values are standardised to linear TPM in long format, and missing values are removed. This produces 8 harmonized CSV files in `harmonized_data/`.

2. **Parquet conversion** — `data_prepare/csv_to_parquet.py` converts each CSV to Apache Parquet using PyArrow with Snappy compression, dictionary-encoding string columns and processing large tables in 500,000-row chunks.

3. **DuckDB views** — At backend startup, `database.py` registers each Parquet file as a named view in an in-memory DuckDB instance (512 MB memory limit, 2 threads), so the data-access layer issues standard SQL without file handling.

### Parquet files

| View name | File | Rows |
|-----------|------|------|
| dim_cell_lines | dim_cell_lines.parquet | 2,220 |
| dim_genes | dim_genes.parquet | 20,135 |
| fact_expression_depmap | fact_expression_depmap.parquet | ~80M |
| fact_expression_hpa | fact_expression_hpa.parquet | ~24M |
| fact_expression_geo | fact_expression_geo.parquet | ~65M |
| fact_proteomics | fact_proteomics.parquet | ~4.7M |
| fact_mutations | fact_mutations.parquet | ~193K |
| fact_fusions | fact_fusions.parquet | ~25K |
| fact_metabolomics | metabolomics_clean.parquet | — |
| fact_mirna | mirna_clean.parquet | — |
| fact_signatures | signatures_clean.parquet | — |
| dim_cell_line_parents | dim_cell_line_parents.parquet | — |

Additional similarity matrices (`sim_expression.parquet`, `sim_proteomics.parquet`, etc.) are precomputed for the cosine similarity feature.

---

## Deployment

The application is deployed on a single Amazon EC2 instance (`t3.medium`, Ubuntu 22.04). Nginx serves the compiled React frontend as static files and reverse-proxies `/api` requests to the FastAPI backend running under systemd/Uvicorn. HTTPS is provided by Certbot (Let's Encrypt).

A GitHub Actions workflow (`.github/workflows/deploy.yml`) triggers on every push to `mew/ranking-v2`: it connects over SSH, pulls the latest code, rebuilds dependencies, restarts the service, and runs a health check.

See `docs/deploy_ec2.md` for the full step-by-step deployment guide.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/genes/search?q=EGF` | Gene autocomplete |
| GET | `/api/genes/resolve/{hugo}` | Symbol → Ensembl resolution |
| POST | `/api/rank` | Rank cell lines by target genes |
| GET | `/api/celllines/{ach_id}` | Cell line metadata |
| GET | `/api/celllines/{ach_id}/evidence` | Per-cell-line evidence breakdown |
| GET | `/api/celllines/{ach_id}/similar` | Top 5 similar cell lines |
| POST | `/api/celllines/compare` | Side-by-side comparison |
| GET | `/api/filters/diseases` | Available disease values |
| GET | `/api/filters/lineages` | Available lineage values |
| GET | `/api/filters/subtypes` | Available subtype values |
| GET | `/api/filters/disease-lineage-mapping` | Valid disease–lineage pairs |
| POST | `/api/chat` | LLM chatbot |

---

## Tech Stack

- **Backend:** Python, FastAPI, DuckDB, Pydantic, scikit-learn, PyArrow
- **Frontend:** React 18, Vite, CSS Modules
- **Data:** Apache Parquet, pandas, NumPy, SciPy
- **LLM:** OpenAI GPT-4o-mini (function-calling API)
- **Deployment:** AWS EC2, Nginx, systemd, Certbot, GitHub Actions CI/CD

---

## Team

**SEMTM0044 2025 — Team 34**
University of Bristol × AstraZeneca

- Mew Yongvibulsiri (2713327)
- Prab Wongsekleo (2829234)
- Nattawas Prakinkij (2800074)
- Victor Oluwabiyi (2819130)

---

## License

This project was developed as part of an MSc dissertation. Please contact the authors for usage permissions.
