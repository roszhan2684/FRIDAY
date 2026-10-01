"""Tests for macOS automation — mocks subprocess so nothing actually opens."""
import pytest
from unittest.mock import patch, MagicMock
from modules.automation.mac_actions import MacActionExecutor
from shared.schemas import ToolCall, ActionSafety


@pytest.fixture
def executor():
    return MacActionExecutor()


def make_call(tool: str, **kwargs) -> ToolCall:
    return ToolCall(tool=tool, args=kwargs, spoken_response="", confidence=1.0)


@patch("subprocess.run")
def test_open_app_success(mock_run, executor):
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    result = executor.execute(make_call("open_app", name="Spotify"))
    assert result.success
    mock_run.assert_called()


@patch("subprocess.run")
def test_open_url_adds_https(mock_run, executor):
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    result = executor._tool_open_url("github.com")
    assert result.success
    args = mock_run.call_args[0][0]
    assert "https://github.com" in args


@patch("subprocess.run")
def test_open_url_passthrough_https(mock_run, executor):
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    result = executor._tool_open_url("https://example.com")
    args = mock_run.call_args[0][0]
    assert "https://example.com" in args


def test_respond_only_always_succeeds(executor):
    result = executor._tool_respond_only("Hello, Boss.")
    assert result.success
    assert result.output == "Hello, Boss."


def test_unknown_tool_returns_error(executor):
    result = executor.execute(make_call("does_not_exist"))
    assert not result.success
    assert "Unknown tool" in result.error


@patch("subprocess.run")
def test_open_app_fallback_spotlight(mock_run, executor):
    # First call (open -a) fails, second call (spotlight find) succeeds
    mock_run.side_effect = [
        MagicMock(returncode=1, stderr="not found"),
        MagicMock(returncode=0, stdout="/Applications/MyApp.app\n"),
        MagicMock(returncode=0),
    ]
    result = executor._tool_open_app("MyApp")
    assert result.success
