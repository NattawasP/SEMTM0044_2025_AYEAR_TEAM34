from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Find lung cancer cells for adherent screen",
                "history": None
            }
        }


class ChatResponse(BaseModel):
    answer: str
    tool_calls: List[Dict[str, Any]] = []
    history: List[Dict[str, Any]] = []


class HealthResponse(BaseModel):
    status: str
    version: str