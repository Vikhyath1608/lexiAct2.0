"""app/schemas/agent.py"""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    website: str = Field(..., description="Target URL")
    goal: str = Field(..., description="What the agent should accomplish")
    session_id: str | None = None


class HumanInputRequest(BaseModel):
    session_id: str
    answer: str


class AgentStatusResponse(BaseModel):
    session_id: str
    status: str
    current_step: int
    total_plan_steps: int
    pending_question: str | None
    visited_urls: list[str]
    extracted_data: dict[str, Any]


class EventType(str, Enum):
    STEP = "step"
    ACTION = "action"
    PAGE_CHANGE = "page_change"
    HUMAN_INPUT = "human_input"
    ERROR = "error"
    DONE = "done"


class SSEEvent(BaseModel):
    event: EventType
    session_id: str
    message: str
    data: dict = Field(default_factory=dict)
