"""Tool registry — every action FRIDAY can take is defined here.

Each tool has:
  - name: identifier used in LLM output
  - description: used in the system prompt
  - args_schema: dict describing expected arguments
  - safety: safe | confirm | blocked
"""
from __future__ import annotations
from dataclasses import dataclass, field
from shared.constants import SAFE_TOOLS, CONFIRM_TOOLS
from shared.schemas import ActionSafety


@dataclass
class ToolDef:
    name: str
    description: str
    args_schema: dict
    safety: ActionSafety = ActionSafety.SAFE
    example: str = ""


TOOL_REGISTRY: list[ToolDef] = [
    ToolDef(
        name="open_file",
        description="Find and open a file on the user's Mac by natural language name or alias (e.g. 'resume', 'portfolio', 'pitch deck'). Searches aliases first, then Spotlight.",
        args_schema={"query": "str — the natural language name", "hint": "str? — optional hint like 'most recent' or 'pdf'"},
        example='{"tool": "open_file", "args": {"query": "resume", "hint": "pdf"}}',
    ),
    ToolDef(
        name="reveal_in_finder",
        description="Find a file and reveal it in Finder without opening it.",
        args_schema={"query": "str"},
    ),
    ToolDef(
        name="search_files",
        description="Search for files and return a list of matches. Use when user wants to see options.",
        args_schema={"query": "str", "limit": "int? — max results, default 5"},
    ),
    ToolDef(
        name="open_app",
        description="Launch or switch to a macOS application by name.",
        args_schema={"name": "str — the app name e.g. 'Cursor', 'Spotify', 'Terminal'"},
        example='{"tool": "open_app", "args": {"name": "Cursor"}}',
    ),
    ToolDef(
        name="switch_app",
        description="Switch focus to an already-running application.",
        args_schema={"name": "str"},
    ),
    ToolDef(
        name="open_url",
        description="Open a URL in the default browser.",
        args_schema={"url": "str — full URL"},
        example='{"tool": "open_url", "args": {"url": "https://github.com"}}',
    ),
    ToolDef(
        name="run_routine",
        description="Execute a saved routine by name (e.g. 'Morning Mode', 'Coding Mode', 'Job Hunt Mode', 'Interview Mode').",
        args_schema={"name": "str — routine name"},
    ),
    ToolDef(
        name="search_youtube",
        description="Search YouTube for a query and open the results page in the browser.",
        args_schema={"query": "str — what to search on YouTube"},
        example='{"tool": "search_youtube", "args": {"query": "lo-fi hip hop"}}',
    ),
    ToolDef(
        name="lookup_movie",
        description="Look up where to watch a movie or show — opens JustWatch search so the user can see all streaming platforms.",
        args_schema={"title": "str — movie or show title"},
        example='{"tool": "lookup_movie", "args": {"title": "Inception"}}',
    ),
    ToolDef(
        name="search_web",
        description="Open a web search in the default browser for a query.",
        args_schema={"query": "str — search query"},
    ),
    ToolDef(
        name="run_custom_command",
        description="Execute a user-defined personal command from the registry — opens their saved sites, files, and apps in the right browser profile.",
        args_schema={"trigger": "str — the trigger phrase the user said"},
        example='{"tool": "run_custom_command", "args": {"trigger": "i want to apply for jobs"}}',
    ),
    ToolDef(
        name="open_url_chrome_profile",
        description="Open a URL in Chrome using a specific profile or account email.",
        args_schema={"url": "str", "profile": "str — email or profile name"},
    ),
    # ─── Reminders ─────────────────────────────────────────────────────────────
    ToolDef(
        name="create_reminder",
        description="Create a reminder from natural language. Extracts time, place, and task automatically.",
        args_schema={"text": "str — full reminder request as user said it"},
        example='{"tool": "create_reminder", "args": {"text": "remind me to go to Target at 2 PM to buy avocados"}}',
    ),
    ToolDef(
        name="query_reminders",
        description="List pending reminders for today or all upcoming.",
        args_schema={"scope": "str? — 'today' (default) or 'all'"},
    ),
    ToolDef(
        name="snooze_reminder",
        description="Snooze a reminder by partial text match — push it forward by N minutes.",
        args_schema={"text": "str — partial text of the reminder", "minutes": "int? — default 30"},
        example='{"tool": "snooze_reminder", "args": {"text": "call mom", "minutes": 30}}',
    ),
    ToolDef(
        name="complete_reminder",
        description="Mark a reminder as done by partial text match.",
        args_schema={"text": "str — partial text of the reminder to mark done"},
        example='{"tool": "complete_reminder", "args": {"text": "call mom"}}',
    ),
    ToolDef(
        name="check_shopping_item",
        description="Check off an item from the shopping list as bought.",
        args_schema={"item": "str — item name to check off"},
    ),
    ToolDef(
        name="clear_shopping_list",
        description="Clear all checked items from the shopping list.",
        args_schema={},
    ),
    ToolDef(
        name="add_shopping_item",
        description="Add one or more items to the shopping list.",
        args_schema={"item": "str", "store": "str?", "quantity": "str?"},
        example='{"tool": "add_shopping_item", "args": {"item": "avocados", "store": "Target", "quantity": "3"}}',
    ),
    ToolDef(
        name="query_shopping_list",
        description="Read the current shopping list.",
        args_schema={"store": "str? — filter by store"},
    ),
    # ─── Calendar ───────────────────────────────────────────────────────────────
    ToolDef(
        name="query_schedule",
        description="Answer questions about the user's calendar — today's events, what's next, free/busy windows.",
        args_schema={"question": "str — e.g. 'what do I have today', 'am I free at 3', 'what is next'"},
        example='{"tool": "query_schedule", "args": {"question": "what do I have today"}}',
    ),
    ToolDef(
        name="get_briefing",
        description="Compose and speak a full morning/evening briefing with weather, calendar, and reminders.",
        args_schema={"mode": "str? — 'full' (default) or 'short'"},
    ),
    # ─── Utility ────────────────────────────────────────────────────────────────
    ToolDef(
        name="respond_only",
        description="Speak a response to the user without taking any other action. Use for greetings, acknowledgements, or answers to questions.",
        args_schema={"message": "str — the message to speak"},
    ),
    ToolDef(
        name="show_history",
        description="Show the user's recent command history in the UI.",
        args_schema={},
    ),
    # ─── Phase 6: Second Brain + Reflection + Job Copilot ──────────────────────
    ToolDef(
        name="capture_note",
        description="Save a quick note, idea, or todo to the second brain.",
        args_schema={"text": "str — the note to save", "category": "str? — general|idea|todo|meeting|learning"},
        example='{"tool": "capture_note", "args": {"text": "Look into FastAPI streaming responses", "category": "learning"}}',
    ),
    ToolDef(
        name="show_notes",
        description="Show notes saved to the second brain.",
        args_schema={"category": "str? — filter by category"},
    ),
    ToolDef(
        name="daily_reflection",
        description="Give a spoken end-of-day summary of what was done today, pending reminders, and shopping list.",
        args_schema={},
    ),
    ToolDef(
        name="open_job_sites",
        description="Open all job sites (JobRight, Glassdoor, LinkedIn) in the job Chrome profile.",
        args_schema={},
    ),
    ToolDef(
        name="research_company",
        description="Open Google and LinkedIn search for a specific company.",
        args_schema={"company": "str — company name"},
    ),
    ToolDef(
        name="set_preference",
        description="Save a user preference (e.g. preferred browser, default file type).",
        args_schema={"key": "str", "value": "str"},
        safety=ActionSafety.CONFIRM,
    ),
    ToolDef(
        name="create_routine",
        description="Create a new named routine from a list of steps.",
        args_schema={
            "name": "str",
            "steps": "list of {tool, args, spoken_before, delay_seconds}",
            "trigger_phrases": "list of str",
        },
        safety=ActionSafety.CONFIRM,
    ),
    ToolDef(
        name="clear_memory",
        description="Clear learned aliases, corrections, or all memory. Use with caution.",
        args_schema={"type": "str — 'aliases' | 'corrections' | 'all'"},
        safety=ActionSafety.CONFIRM,
    ),
]

TOOL_MAP: dict[str, ToolDef] = {t.name: t for t in TOOL_REGISTRY}


def tool_schema_for_prompt() -> str:
    """Format tool list for injection into the LLM system prompt."""
    lines = []
    for t in TOOL_REGISTRY:
        args_str = ", ".join(f"{k}: {v}" for k, v in t.args_schema.items())
        lines.append(f"- {t.name}({args_str}): {t.description}")
    return "\n".join(lines)


def get_safety(tool_name: str) -> ActionSafety:
    tool = TOOL_MAP.get(tool_name)
    if tool:
        return tool.safety
    if tool_name in SAFE_TOOLS:
        return ActionSafety.SAFE
    if tool_name in CONFIRM_TOOLS:
        return ActionSafety.CONFIRM
    return ActionSafety.BLOCKED
