from fastapi import APIRouter, HTTPException
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat_agent import chat
from .schemas import ChatRequest, ChatResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok", "version": "1.0"}


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        answer = chat(request.message)
        return {
            "answer": answer,
            "tool_calls": [],
            "history": [
                *(request.history or []),
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": answer}
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
def list_tools():
    from chat_agent import TOOLS
    return {
        "tools": [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"]
            }
            for t in TOOLS
        ]
    }