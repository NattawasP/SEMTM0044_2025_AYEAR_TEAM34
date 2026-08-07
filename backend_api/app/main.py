"""
FastAPI application assembly.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers import genes, ranking, celllines, filters

app = FastAPI(
    title="CellLineFinder API",
    version="0.1.0",
    description="Multi-omics cell line recommendation engine",
)

# CORS — allow the React frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(genes.router)
app.include_router(ranking.router)
app.include_router(celllines.router)
app.include_router(filters.router)


@app.get("/")
def root():
    return {"name": "CellLineFinder API", "version": "0.1.0", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}
