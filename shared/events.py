"""WebSocket event types broadcast from runtime to Swift UI."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class RuntimeEvent(BaseModel):
    """Base event sent over WebSocket to the Swift app."""
    type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)


def state_event(state: str) -> RuntimeEvent:
    return RuntimeEvent(type="state_change", payload={"state": state})


def transcript_event(text: str, confidence: float, low_confidence: bool) -> RuntimeEvent:
    return RuntimeEvent(
        type="transcript",
        payload={"text": text, "confidence": confidence, "low_confidence": low_confidence},
    )


def action_event(tool: str, spoken: str) -> RuntimeEvent:
    return RuntimeEvent(
        type="action",
        payload={"tool": tool, "spoken_response": spoken},
    )


def result_event(success: bool, output: str, error: str | None = None) -> RuntimeEvent:
    return RuntimeEvent(
        type="result",
        payload={"success": success, "output": output, "error": error},
    )


def confirm_event(tool: str, args: dict, spoken: str) -> RuntimeEvent:
    """Sent when an action requires user confirmation before executing."""
    return RuntimeEvent(
        type="confirm_required",
        payload={"tool": tool, "args": args, "spoken": spoken},
    )


def error_event(message: str) -> RuntimeEvent:
    return RuntimeEvent(type="error", payload={"message": message})
