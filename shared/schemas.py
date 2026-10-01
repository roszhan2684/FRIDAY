"""Central Pydantic schemas for all FRIDAY data structures."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import uuid


# ─── Enums ────────────────────────────────────────────────────────────────────

class ActionSafety(str, Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    BLOCKED = "blocked"


class PipelineState(str, Enum):
    IDLE = "idle"
    LISTENING_FOR_WAKE = "listening_for_wake"
    CAPTURING = "capturing"
    TRANSCRIBING = "transcribing"
    PLANNING = "planning"
    CONFIRMING = "confirming"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    ERROR = "error"


class OutcomeStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"
    CORRECTED = "corrected"


# ─── Core Audio / STT ─────────────────────────────────────────────────────────

class Transcript(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    audio_hash: str
    duration_seconds: float
    model: str = "whisper-medium"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CorrectionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audio_hash: str
    bad_transcript: str
    corrected_text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── LLM Planning ─────────────────────────────────────────────────────────────

class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    spoken_response: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    safety: ActionSafety = ActionSafety.SAFE


class PlanResult(BaseModel):
    tool_call: ToolCall
    raw_llm_output: str
    planning_ms: int


# ─── Action Execution ─────────────────────────────────────────────────────────

class ActionResult(BaseModel):
    success: bool
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Memory ───────────────────────────────────────────────────────────────────

class LearnedAlias(BaseModel):
    phrase: str
    resolved_path: str
    file_type: str = ""
    confidence: float = 1.0
    use_count: int = 1
    last_used: datetime = Field(default_factory=datetime.utcnow)


class UserPreference(BaseModel):
    key: str
    value: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Routines ─────────────────────────────────────────────────────────────────

class RoutineStep(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    spoken_before: str = ""
    delay_seconds: float = 0.0


class Routine(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    trigger_phrases: list[str] = Field(default_factory=list)
    steps: list[RoutineStep]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    use_count: int = 0


# ─── Interaction Logging ───────────────────────────────────────────────────────

class InteractionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    transcript: str
    audio_hash: str | None = None
    confidence: float | None = None
    tool_called: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    spoken_response: str = ""
    outcome: OutcomeStatus = OutcomeStatus.SUCCESS
    error: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── API Request / Response ───────────────────────────────────────────────────

class CommandRequest(BaseModel):
    text: str
    source: str = "typed"


class CommandResponse(BaseModel):
    transcript: str
    tool_called: str
    spoken_response: str
    success: bool
    output: str = ""
    error: str | None = None


class CorrectionRequest(BaseModel):
    audio_hash: str
    bad_transcript: str
    corrected_text: str
