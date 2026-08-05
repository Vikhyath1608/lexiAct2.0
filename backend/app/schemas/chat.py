"""app/schemas/chat.py"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    session_id: str = Field(default="default")


class ChatResponse(BaseModel):
    response: str
    session_id: str
    automation_triggered: bool = False
    automation_type: Optional[str] = None


class ConversationEntry(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[ConversationEntry]
    total: int
    limit: int
    offset: int


class SessionsResponse(BaseModel):
    sessions: list[str]
    total: int
    limit: int
    offset: int
