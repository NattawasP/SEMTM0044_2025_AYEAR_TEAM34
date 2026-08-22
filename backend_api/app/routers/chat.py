"""
Chat router — /api/chat endpoint for the CellLineFinder chatbot.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.chat_service import chat


router = APIRouter(prefix="/api", tags=["chat"])


# ── Request / Response models ────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Find lung cancer cells for adherent screen",
                "history": None,
            }
        }
    }


class ChatResponse(BaseModel):
    answer: str
    tool_calls_made: list[str] = []
    history: list[dict] = []


# ── Endpoints ────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """Ask the CellLineFinder chatbot a question."""
    try:
        result = chat(req.message, history=req.history)
        return result
    except RuntimeError as e:
        # e.g. missing API key
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
