from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router


app = FastAPI(
    title="CellLineFinder API",
    description="Chat agent for cell line search using LLM function calling",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": "CellLineFinder API",
        "docs": "/docs",
        "health": "/api/v1/health"
    }