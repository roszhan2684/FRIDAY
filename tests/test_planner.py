"""Tests for the LLM planner — mocks Ollama so no model needed."""
import json
import pytest
from unittest.mock import MagicMock, patch
from modules.llm.planner import Planner
from shared.schemas import ActionSafety


@pytest.fixture
def planner():
    p = Planner()
    return p


def test_parse_valid_tool_call(planner):
    raw = json.dumps({
        "tool": "open_file",
        "args": {"query": "resume", "hint": "pdf"},
        "spoken_response": "Opening your resume, Boss.",
        "confidence": 0.95,
    })
    tc = planner._parse_tool_call(raw, "open my resume")
    assert tc.tool == "open_file"
    assert tc.args["query"] == "resume"
    assert tc.confidence == 0.95
    assert tc.safety == ActionSafety.SAFE


def test_parse_malformed_json_falls_back(planner):
    tc = planner._parse_tool_call("not json at all {{{", "what")
    assert tc.tool == "respond_only"
    assert tc.confidence <= 0.3  # rule-based fallback gives low confidence


def test_parse_strips_markdown_fences(planner):
    raw = "```json\n" + json.dumps({
        "tool": "open_app",
        "args": {"name": "Spotify"},
        "spoken_response": "Opening Spotify, Boss.",
        "confidence": 0.99,
    }) + "\n```"
    tc = planner._parse_tool_call(raw, "open spotify")
    assert tc.tool == "open_app"


def test_fallback_plan_open(planner):
    raw = planner._fallback_plan("open cursor")
    data = json.loads(raw)
    assert data["tool"] == "open_app"


def test_fallback_plan_unknown(planner):
    raw = planner._fallback_plan("do something weird")
    data = json.loads(raw)
    assert data["tool"] == "respond_only"


def test_confirm_tool_gets_confirm_safety(planner):
    raw = json.dumps({
        "tool": "clear_memory",
        "args": {"type": "all"},
        "spoken_response": "Clearing memory, Boss.",
        "confidence": 0.9,
    })
    tc = planner._parse_tool_call(raw, "clear all memory")
    assert tc.safety == ActionSafety.CONFIRM


@patch("httpx.Client.post")
def test_plan_with_mocked_ollama(mock_post, planner):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "content": json.dumps({
                "tool": "run_routine",
                "args": {"name": "Morning Mode"},
                "spoken_response": "Good morning, Boss.",
                "confidence": 0.98,
            })
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    result = planner.plan("morning mode")
    assert result.tool_call.tool == "run_routine"
    assert result.tool_call.args["name"] == "Morning Mode"
    assert result.planning_ms >= 0
