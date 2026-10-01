"""LLM-based intent planner — converts a transcript into a structured ToolCall.

Uses Ollama for local inference. Returns structured JSON parsed into ToolCall.
Includes tool-name normalization so hallucinated names map to real tools.
"""
from __future__ import annotations
import json
import logging
import re
import time
from typing import Any

import httpx

from modules.llm.tools import tool_schema_for_prompt, TOOL_MAP, get_safety
from shared.schemas import ToolCall, PlanResult, ActionSafety
from shared.constants import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# ─── Tool name normalization ───────────────────────────────────────────────────
# LLMs often hallucinate variant names. Map them to the real tool names.

TOOL_ALIASES: dict[str, str] = {
    # run_routine variants
    "toggle_morning_mode": "run_routine",
    "morning_mode": "run_routine",
    "activate_morning_mode": "run_routine",
    "run_mode": "run_routine",
    "switch_mode": "run_routine",        # llama3.2 commonly hallucinates this
    "set_mode": "run_routine",
    "enable_mode": "run_routine",
    "activate_mode": "run_routine",
    "activate_routine": "run_routine",
    "start_routine": "run_routine",
    "execute_routine": "run_routine",
    "coding_mode": "run_routine",
    "job_hunt_mode": "run_routine",
    "interview_mode": "run_routine",
    # open_app variants
    "launch_app": "open_app",
    "start_app": "open_app",
    "open_application": "open_app",
    "open_program": "open_app",
    # open_url variants
    "open_website": "open_url",
    "open_browser": "open_url",
    "navigate_to": "open_url",
    # open_file variants
    "find_and_open_file": "open_file",
    "open_document": "open_file",
    # search_files variants
    "search_file": "search_files",
    "find_file": "search_files",
    "find_files": "search_files",
    "search_documents": "search_files",
    # weather variants
    "check_weather": "get_weather",
    "get_weather_forecast": "get_weather",
    "weather_check": "get_weather",
    "show_weather": "get_weather",
    "weather_update": "get_weather",
    # reflection/activity variants
    "list_activities": "daily_reflection",
    "get_activities": "daily_reflection",
    "show_activities": "daily_reflection",
    "activity_summary": "daily_reflection",
    # date/time — map to respond_only
    "check_day_of_week": "respond_only",
    "get_date": "respond_only",
    "get_time": "respond_only",
    "check_date": "respond_only",
    # schedule variants
    "check_schedule": "query_schedule",
    "get_schedule": "query_schedule",
    "show_schedule": "query_schedule",
}

# When an aliased tool name carries implicit routine name in the tool itself
ROUTINE_FROM_TOOL: dict[str, str] = {
    "toggle_morning_mode": "Morning Mode",
    "morning_mode": "Morning Mode",
    "activate_morning_mode": "Morning Mode",
    "coding_mode": "Coding Mode",
    "job_hunt_mode": "Job Hunt Mode",
    "interview_mode": "Interview Mode",
}

# ─── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are FRIDAY, a local macOS assistant. Parse commands into JSON tool calls.

ALLOWED TOOL NAMES (use EXACTLY these, no others):
{tool_names}

Tool descriptions:
{tools}

User aliases: {aliases}
Recent commands: {recent}

STRICT RULES:
1. Output ONLY valid JSON. No markdown. No explanation. No text outside the JSON.
2. The "tool" field MUST be one of the allowed tool names above — nothing else.
3. spoken_response: short (under 12 words), address user as "Boss".
4. For routines say "run_routine" with the routine name in args.

Output format — exactly this structure:
{{"tool": "<exact_tool_name>", "args": {{...}}, "spoken_response": "<short>", "confidence": 0.0}}"""

FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "open my resume"},
    {"role": "assistant", "content": '{"tool": "open_file", "args": {"query": "resume", "hint": "pdf"}, "spoken_response": "Opening your resume, Boss.", "confidence": 0.95}'},
    {"role": "user", "content": "search the web for software engineer jobs"},
    {"role": "assistant", "content": '{"tool": "search_web", "args": {"query": "software engineer jobs"}, "spoken_response": "Searching the web, Boss.", "confidence": 0.99}'},
    {"role": "user", "content": "search youtube for lo fi music"},
    {"role": "assistant", "content": '{"tool": "search_youtube", "args": {"query": "lo fi music"}, "spoken_response": "Searching YouTube, Boss.", "confidence": 0.99}'},
    {"role": "user", "content": "where can i watch inception"},
    {"role": "assistant", "content": '{"tool": "lookup_movie", "args": {"title": "Inception"}, "spoken_response": "Looking up Inception, Boss.", "confidence": 0.99}'},
    {"role": "user", "content": "remind me tonight to call mom"},
    {"role": "assistant", "content": '{"tool": "create_reminder", "args": {"text": "remind me tonight to call mom"}, "spoken_response": "Saved, Boss.", "confidence": 0.99}'},
    {"role": "user", "content": "add 3 avocados at Target to shopping list"},
    {"role": "assistant", "content": '{"tool": "add_shopping_item", "args": {"item": "avocados", "store": "Target", "quantity": "3"}, "spoken_response": "Added, Boss.", "confidence": 0.99}'},
    {"role": "user", "content": "snooze the call mom reminder for 30 minutes"},
    {"role": "assistant", "content": '{"tool": "snooze_reminder", "args": {"text": "call mom", "minutes": 30}, "spoken_response": "Snoozed, Boss.", "confidence": 0.99}'},
    {"role": "user", "content": "research Google"},
    {"role": "assistant", "content": '{"tool": "research_company", "args": {"company": "Google"}, "spoken_response": "Researching Google, Boss.", "confidence": 0.99}'},
    {"role": "user", "content": "open github.com"},
    {"role": "assistant", "content": '{"tool": "open_url", "args": {"url": "https://github.com"}, "spoken_response": "Opening GitHub, Boss.", "confidence": 0.99}'},
    {"role": "user", "content": "search for my resume"},
    {"role": "assistant", "content": '{"tool": "search_files", "args": {"query": "resume"}, "spoken_response": "Searching, Boss.", "confidence": 0.95}'},
]


class Planner:
    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: int = OLLAMA_TIMEOUT_SECONDS,
    ):
        self._model = model
        self._base_url = base_url
        self._timeout = timeout
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def plan(
        self,
        transcript: str,
        aliases: dict[str, str] | None = None,
        recent_commands: list[str] | None = None,
    ) -> PlanResult:
        start = time.monotonic()

        # ── Pre-filter 1: check personal command registry ──────────────────────
        registry_tc = self._check_registry(transcript)
        if registry_tc:
            ms = int((time.monotonic() - start) * 1000)
            logger.info("Registry hit: %r → %s (%dms)", transcript, registry_tc.tool, ms)
            return PlanResult(tool_call=registry_tc, raw_llm_output="[registry]", planning_ms=ms)

        # ── Pre-filter 2: high-confidence rule-based for known pattern classes ──
        pre_tc = self._pre_filter(transcript)
        if pre_tc:
            ms = int((time.monotonic() - start) * 1000)
            logger.info("Pre-filter hit: %r → %s (%dms)", transcript, pre_tc.tool, ms)
            return PlanResult(tool_call=pre_tc, raw_llm_output="[pre-filter]", planning_ms=ms)

        tool_names = ", ".join(sorted(TOOL_MAP.keys()))
        system = SYSTEM_PROMPT.format(
            tool_names=tool_names,
            tools=tool_schema_for_prompt(),
            aliases=json.dumps(aliases or {}, indent=2) if aliases else "none",
            recent=json.dumps((recent_commands or [])[:5]) if recent_commands else "none",
        )

        messages = [*FEW_SHOT_EXAMPLES, {"role": "user", "content": transcript}]

        try:
            response = self._client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "system": system,
                    "stream": False,
                    "options": {
                        "temperature": 0.05,
                        "num_predict": 80,
                        "num_ctx": 2048,
                    },
                },
            )
            response.raise_for_status()
            raw = response.json()["message"]["content"].strip()

        except httpx.TimeoutException:
            logger.error("Ollama timed out for transcript: %r", transcript)
            raw = self._fallback_plan(transcript)
        except Exception as exc:
            logger.exception("Planner error: %s", exc)
            raw = self._fallback_plan(transcript)

        planning_ms = int((time.monotonic() - start) * 1000)
        tool_call = self._parse_tool_call(raw, transcript)

        logger.debug("Planned %r → %s (%.0fms)", transcript, tool_call.tool, planning_ms)
        return PlanResult(tool_call=tool_call, raw_llm_output=raw, planning_ms=planning_ms)

    def _parse_tool_call(self, raw: str, original_transcript: str) -> ToolCall:
        try:
            clean = self._extract_json(raw)
            data = json.loads(clean)

            tool_name = data.get("tool", "respond_only")
            args: dict[str, Any] = data.get("args", {})
            spoken = data.get("spoken_response", "Done, Boss.")
            confidence = float(data.get("confidence", 0.8))

            # Normalize hallucinated tool names → real tool names
            tool_name, args = self._normalize_tool(tool_name, args)

            # If LLM/normalization yields respond_only, always try rule-based as rescue pass
            if tool_name == "respond_only":
                rule_tc = self._rule_based_parse(original_transcript)
                if rule_tc.tool != "respond_only":
                    logger.info("Rule-based rescue: %r → %s", original_transcript, rule_tc.tool)
                    return rule_tc

            safety = get_safety(tool_name)
            return ToolCall(
                tool=tool_name,
                args=args,
                spoken_response=spoken,
                confidence=confidence,
                safety=safety,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("LLM output parse failed: %s — raw: %r", exc, raw[:100])
            return self._rule_based_parse(original_transcript)

    def _normalize_tool(self, tool_name: str, args: dict) -> tuple[str, dict]:
        """Map hallucinated tool names to real ones. Fix args if needed."""
        if tool_name in TOOL_MAP:
            return tool_name, args

        normalized = TOOL_ALIASES.get(tool_name)
        if not normalized:
            # Try fuzzy: strip underscores/spaces, check partial match
            slug = tool_name.lower().replace("-", "_")
            for real_name in TOOL_MAP:
                if slug.startswith(real_name) or real_name.startswith(slug):
                    normalized = real_name
                    break

        if not normalized:
            logger.warning("Unknown tool %r — using respond_only", tool_name)
            return "respond_only", {"message": "I'm not sure how to do that, Boss."}

        # For routine aliases: ensure args has "name" key
        if normalized == "run_routine":
            # Remap "mode" arg key → "name" (LLM often uses {"mode": "X"})
            if "mode" in args and "name" not in args:
                args = {"name": args["mode"]}
            if "name" not in args:
                routine_name = ROUTINE_FROM_TOOL.get(tool_name)
                if routine_name:
                    args = {"name": routine_name}
                else:
                    parts = (
                        tool_name.replace("activate_", "").replace("toggle_", "")
                        .replace("switch_", "").replace("set_", "").replace("enable_", "")
                        .replace("_mode", " Mode").replace("_", " ")
                    )
                    args = {"name": parts.title()}

        logger.info("Tool alias: %r → %r (args: %s)", tool_name, normalized, args)
        return normalized, args

    @staticmethod
    def _extract_json(raw: str) -> str:
        """Extract JSON object from raw LLM output, handling markdown fences."""
        s = raw.strip()
        # Strip markdown code fences
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?", "", s).rstrip("`").strip()
        # Find the outermost JSON object
        start = s.find("{")
        end = s.rfind("}") + 1
        if start != -1 and end > start:
            return s[start:end]
        return s

    def _rule_based_parse(self, transcript: str) -> ToolCall:
        """Keyword-based fallback when LLM output is completely unparseable."""
        t = transcript.lower().strip()

        routine_keywords = {
            "morning mode": "Morning Mode",
            "good morning": "Morning Mode",
            "start my day": "Morning Mode",
            "coding mode": "Coding Mode",
            "let us code": "Coding Mode",
            "code mode": "Coding Mode",
            "job hunt": "Job Hunt Mode",
            "job search": "Job Hunt Mode",
            "hunting mode": "Job Hunt Mode",
            "apply jobs": "Job Hunt Mode",
            "let's apply": "Job Hunt Mode",
            "lets apply": "Job Hunt Mode",
            "apply for jobs": "Job Hunt Mode",
            "interview mode": "Interview Mode",
            "interview prep": "Interview Mode",
            "prep for interview": "Interview Mode",
        }
        for phrase, routine_name in routine_keywords.items():
            if phrase in t:
                return ToolCall(
                    tool="run_routine",
                    args={"name": routine_name},
                    spoken_response=f"Running {routine_name}, Boss.",
                    confidence=0.7,
                    safety=ActionSafety.SAFE,
                )

        if any(w in t for w in ["open", "launch", "start", "show"]):
            # Detect URL
            url_match = re.search(r"(https?://\S+|\S+\.\S{2,4})", t)
            if url_match:
                url = url_match.group(1)
                if not url.startswith("http"):
                    url = "https://" + url
                return ToolCall(
                    tool="open_url",
                    args={"url": url},
                    spoken_response=f"Opening that, Boss.",
                    confidence=0.6,
                    safety=ActionSafety.SAFE,
                )
            words = [w for w in t.split() if w not in ("open", "launch", "start", "show", "the", "my", "a")]
            name = words[-1].capitalize() if words else "app"
            return ToolCall(
                tool="open_app",
                args={"name": name},
                spoken_response=f"Opening {name}, Boss.",
                confidence=0.5,
                safety=ActionSafety.SAFE,
            )

        if "youtube" in t and any(w in t for w in ["search", "find", "look", "play", "watch"]):
            words = [w for w in t.split() if w not in ("search", "find", "look", "for", "on", "youtube", "play", "watch")]
            query = " ".join(words)
            return ToolCall(
                tool="search_youtube", args={"query": query},
                spoken_response=f"Searching YouTube for {query}, Boss.",
                confidence=0.8, safety=ActionSafety.SAFE,
            )

        if any(p in t for p in ["where can i watch", "where to watch", "how to watch", "stream", "streaming"]):
            words = [w for w in t.split() if w not in ("where", "can", "i", "watch", "how", "to", "stream", "streaming", "find", "the")]
            title = " ".join(words)
            return ToolCall(
                tool="lookup_movie", args={"title": title},
                spoken_response=f"Looking up where to watch {title}, Boss.",
                confidence=0.75, safety=ActionSafety.SAFE,
            )

        # Query reminders (must come before create_reminder to avoid "reminders" collision)
        if any(p in t for p in ["what are my reminder", "show my reminder",
                                  "list my reminder", "any reminder"]):
            return ToolCall(
                tool="query_reminders", args={"scope": "today"},
                spoken_response="Here are your reminders, Boss.", confidence=0.93, safety=ActionSafety.SAFE,
            )

        # Query shopping list
        if any(p in t for p in ["what is on my shopping", "what's on my shopping",
                                  "show my shopping list", "shopping list have",
                                  "what do i need to buy"]):
            return ToolCall(
                tool="query_shopping_list", args={},
                spoken_response="Here is your shopping list, Boss.", confidence=0.93, safety=ActionSafety.SAFE,
            )

        # Reminders creation ("note that" handled by capture_note, "reminders" query handled above)
        if any(t.startswith(p) for p in ["remind me", "don't let me forget"]) or \
           re.search(r"\bremind me\b", t):
            return ToolCall(
                tool="create_reminder", args={"text": transcript},
                spoken_response="Got it, Boss. Reminder saved.",
                confidence=0.85, safety=ActionSafety.SAFE,
            )

        # Shopping list
        if any(p in t for p in ["add", "put"]) and any(p in t for p in ["shopping list", "grocery", "groceries"]):
            # Extract item
            words = [w for w in t.split() if w not in ("add","put","to","my","the","shopping","list","grocery","groceries","and","in")]
            return ToolCall(
                tool="add_shopping_item", args={"item": " ".join(words)},
                spoken_response=f"Added to your shopping list, Boss.",
                confidence=0.75, safety=ActionSafety.SAFE,
            )

        # Calendar queries
        if any(p in t for p in ["what do i have", "what's on my calendar", "my schedule", "calendar", "any meetings", "anything today"]):
            return ToolCall(
                tool="query_schedule", args={"question": transcript},
                spoken_response="Checking your calendar, Boss.",
                confidence=0.8, safety=ActionSafety.SAFE,
            )

        # Briefing
        if any(p in t for p in ["briefing", "brief me", "what's going on", "what is going on", "daily update", "morning update"]):
            return ToolCall(
                tool="get_briefing", args={"mode": "full"},
                spoken_response="Here is your briefing, Boss.",
                confidence=0.85, safety=ActionSafety.SAFE,
            )

        if any(w in t for w in ["search", "find", "look for"]):
            words = [w for w in t.split() if w not in ("search", "find", "look", "for", "my", "the", "a")]
            query = " ".join(words)
            return ToolCall(
                tool="search_files",
                args={"query": query},
                spoken_response=f"Searching for {query}, Boss.",
                confidence=0.5,
                safety=ActionSafety.SAFE,
            )

        return ToolCall(
            tool="respond_only",
            args={"message": "I'm not sure what you need, Boss. Could you rephrase?"},
            spoken_response="Could you rephrase that, Boss?",
            confidence=0.2,
            safety=ActionSafety.SAFE,
        )

    def _fallback_plan(self, transcript: str) -> str:
        """Minimal JSON fallback when Ollama is unreachable."""
        tc = self._rule_based_parse(transcript)
        return json.dumps({
            "tool": tc.tool,
            "args": tc.args,
            "spoken_response": tc.spoken_response,
            "confidence": tc.confidence,
        })

    def _pre_filter(self, transcript: str) -> ToolCall | None:
        """
        High-confidence rule-based pre-filter. Handles patterns where
        the LLM is unreliable (too many tools, ambiguous phrasing).
        Returns a ToolCall if the pattern matches, None otherwise.
        """
        t = transcript.lower().strip()

        # ── Reminder management (snooze / complete) ───────────────────────────
        if "snooze" in t and any(p in t for p in ["reminder", "the ", "my "]):
            mins = 30
            m = re.search(r"(\d+)\s*(min|minute|hour)", t)
            if m:
                n = int(m.group(1))
                mins = n * 60 if "hour" in m.group(2) else n
            text_hint = re.sub(r"snooze\s+(?:the|my)?\s*", "", t).split("reminder")[0].strip()
            return ToolCall(
                tool="snooze_reminder", args={"text": text_hint or "reminder", "minutes": mins},
                spoken_response=f"Snoozed for {mins} minutes, Boss.",
                confidence=0.9, safety=ActionSafety.SAFE,
            )

        if any(t.startswith(p) for p in ["i called", "i went to", "i bought", "i did", "done with", "finished"]):
            task = re.sub(r"^(i called|i went to|i bought|i did|done with|finished)\s*", "", t).strip()
            return ToolCall(
                tool="complete_reminder", args={"text": task or t},
                spoken_response="Marked done, Boss.", confidence=0.82, safety=ActionSafety.SAFE,
            )

        if any(p in t for p in ["got the ", "bought the ", "picked up "]):
            item = re.sub(r"(got the|bought the|picked up)\s*", "", t).strip()
            return ToolCall(
                tool="check_shopping_item", args={"item": item},
                spoken_response=f"Checked off {item}, Boss.", confidence=0.82, safety=ActionSafety.SAFE,
            )

        # ── Phase 6: Note capture (checked before reminders to avoid collision) ─
        if any(p in t for p in ["note that", "save this", "jot down", "write down", "capture this"]):
            idea_text = re.sub(
                r"^(note that|save this|jot down|write down|capture this)\s*[:–\-]?\s*", "", t
            ).strip()
            cat = ("idea" if any(w in t for w in ["idea", "concept", "thought"]) else
                   "todo" if any(w in t for w in ["need to", "should", "todo"]) else "general")
            return ToolCall(
                tool="capture_note",
                args={"text": idea_text or transcript, "category": cat},
                spoken_response="Noted, Boss.", confidence=0.9, safety=ActionSafety.SAFE,
            )

        # ── Routines (exact mode phrases) ──────────────────────────────────────
        routine_map = {
            "morning mode": "Morning Mode",
            "good morning": "Morning Mode",
            "start my day": "Morning Mode",
            "coding mode": "Coding Mode",
            "code mode": "Coding Mode",
            "let us code": "Coding Mode",
            "start coding": "Coding Mode",
            "study mode": "Study Mode",
            "start study mode": "Study Mode",
            "study time": "Study Mode",
            "let me study": "Study Mode",
            "job hunt mode": "Job Hunt Mode",
            "job hunting": "Job Hunt Mode",
            "job search mode": "Job Hunt Mode",
            "interview mode": "Interview Mode",
            "interview prep": "Interview Mode",
            "lets apply jobs": "Job Hunt Mode",
            "apply for jobs": "Job Hunt Mode",
        }
        for phrase, routine in routine_map.items():
            if phrase in t:
                return ToolCall(
                    tool="run_routine", args={"name": routine},
                    spoken_response=f"Starting {routine}, Boss.",
                    confidence=0.99, safety=ActionSafety.SAFE,
                )

        # ── Reminders ─────────────────────────────────────────────────────────
        if t.startswith("remind me") or re.search(r"\bremind me\b", t):
            return ToolCall(
                tool="create_reminder", args={"text": transcript},
                spoken_response="Got it, Boss. Reminder saved.",
                confidence=0.92, safety=ActionSafety.SAFE,
            )

        # ── Shopping list ──────────────────────────────────────────────────────
        if ("shopping list" in t or "grocery list" in t or "groceries" in t) and \
           any(w in t for w in ["add", "put", "need"]):
            item = re.sub(r"^(add|put)\s+", "", t)
            item = re.sub(r"\s*(to\s+)?(my\s+)?(shopping|grocery)\s+(list|groceries).*$", "", item)
            return ToolCall(
                tool="add_shopping_item", args={"item": item.strip()},
                spoken_response=f"Added to your shopping list, Boss.",
                confidence=0.9, safety=ActionSafety.SAFE,
            )

        # ── Calendar queries ───────────────────────────────────────────────────
        calendar_triggers = [
            "what do i have", "what's on my calendar", "my calendar",
            "any meetings", "anything scheduled", "what's today",
            "am i free", "how busy", "what's next", "next event",
            "anything today", "anything tomorrow",
        ]
        if any(p in t for p in calendar_triggers):
            return ToolCall(
                tool="query_schedule", args={"question": transcript},
                spoken_response="Checking your calendar, Boss.",
                confidence=0.9, safety=ActionSafety.SAFE,
            )

        # ── Briefing ──────────────────────────────────────────────────────────
        if any(p in t for p in ["briefing", "brief me", "daily update", "morning update",
                                  "what's going on", "what is going on", "summary"]):
            return ToolCall(
                tool="get_briefing", args={"mode": "full"},
                spoken_response="Here is your briefing, Boss.",
                confidence=0.9, safety=ActionSafety.SAFE,
            )

        # ── Phase 6: Second brain / note capture ──────────────────────────────
        if any(p in t for p in ["note that", "save this", "remember this",
                                  "capture", "jot down", "write down"]):
            idea_text = re.sub(
                r"^(note that|save this|remember this|capture|jot down|write down)\s*[:–\-]?\s*",
                "", t
            ).strip()
            cat = ("idea" if any(w in t for w in ["idea", "concept", "thought"]) else
                   "todo" if any(w in t for w in ["todo", "to do", "need to", "should"]) else
                   "general")
            return ToolCall(
                tool="capture_note",
                args={"text": idea_text or transcript, "category": cat},
                spoken_response="Noted, Boss.", confidence=0.85, safety=ActionSafety.SAFE,
            )

        # ── Phase 6: Daily reflection ──────────────────────────────────────────
        if any(p in t for p in ["how was my day", "daily reflection",
                                  "end of day", "day summary", "what did i do today"]):
            return ToolCall(
                tool="daily_reflection", args={},
                spoken_response="Here is your day summary, Boss.",
                confidence=0.9, safety=ActionSafety.SAFE,
            )

        # ── Weather ───────────────────────────────────────────────────────────
        if any(p in t for p in ["weather", "temperature", "how hot", "how cold",
                                  "is it raining", "will it rain", "forecast"]):
            return ToolCall(
                tool="get_weather", args={},
                spoken_response="Checking the weather, Boss.",
                confidence=0.97, safety=ActionSafety.SAFE,
            )

        # ── Date / time ───────────────────────────────────────────────────────
        if any(p in t for p in ["what day is", "what's today", "what is today",
                                  "what date", "today's date", "what time"]):
            import datetime
            now = datetime.datetime.now()
            day_str = now.strftime("%A, %B %d")
            time_str = now.strftime("%I:%M %p").lstrip("0")
            msg = f"It's {day_str}. The time is {time_str}."
            return ToolCall(
                tool="respond_only", args={"message": msg},
                spoken_response=msg, confidence=0.99, safety=ActionSafety.SAFE,
            )

        # ── Streaming services ────────────────────────────────────────────────
        streaming_map = {
            "netflix": "https://netflix.com",
            "hulu": "https://hulu.com",
            "disney plus": "https://disneyplus.com",
            "disney+": "https://disneyplus.com",
            "apple tv": "https://tv.apple.com",
            "prime video": "https://primevideo.com",
            "amazon prime": "https://primevideo.com",
            "youtube": "https://youtube.com",
            "twitch": "https://twitch.tv",
            "crunchyroll": "https://crunchyroll.com",
        }
        if any(w in t for w in ["open", "watch", "play", "launch", "start", "go to"]):
            for keyword, url in streaming_map.items():
                if keyword in t:
                    name = keyword.title()
                    return ToolCall(
                        tool="open_url", args={"url": url},
                        spoken_response=f"Opening {name}, Boss.",
                        confidence=0.97, safety=ActionSafety.SAFE,
                    )

        # ── Reminder queries (checked before app opens to avoid "calendar" collision) ─
        reminder_query_triggers = [
            "what are my reminders", "show my reminders", "list my reminders",
            "any reminders", "do i have reminders", "my reminders",
        ]
        if any(p in t for p in reminder_query_triggers):
            return ToolCall(
                tool="query_reminders", args={"scope": "today"},
                spoken_response="Here are your reminders, Boss.",
                confidence=0.95, safety=ActionSafety.SAFE,
            )

        # ── Shopping list query ────────────────────────────────────────────────
        if any(p in t for p in ["shopping list", "grocery list"]) and \
           any(w in t for w in ["what", "show", "read", "tell"]):
            return ToolCall(
                tool="query_shopping_list", args={},
                spoken_response="Here is your shopping list, Boss.",
                confidence=0.95, safety=ActionSafety.SAFE,
            )

        # ── App opens with known app names (no dot = not a URL) ───────────────
        known_apps = {
            "safari": "Safari", "chrome": "Google Chrome", "firefox": "Firefox",
            "spotify": "Spotify", "music": "Music", "vscode": "Visual Studio Code",
            "vs code": "Visual Studio Code", "visual studio code": "Visual Studio Code",
            "terminal": "Terminal", "finder": "Finder", "notes": "Notes",
            "calendar": "Calendar", "mail": "Mail", "messages": "Messages",
            "facetime": "FaceTime", "claude": "Claude", "cursor": "Cursor",
            "xcode": "Xcode", "slack": "Slack", "zoom": "Zoom",
            "discord": "Discord", "notion": "Notion", "figma": "Figma",
            "arc": "Arc", "warp": "Warp",
        }
        if any(w in t for w in ["open", "launch", "start", "switch to"]):
            for keyword, app_name in known_apps.items():
                if keyword in t and "." not in t.split(keyword)[-1][:20]:
                    return ToolCall(
                        tool="open_app", args={"name": app_name},
                        spoken_response=f"Opening {app_name}, Boss.",
                        confidence=0.97, safety=ActionSafety.SAFE,
                    )

        return None

    def _check_registry(self, transcript: str) -> ToolCall | None:
        """Check the personal command registry before hitting Ollama."""
        try:
            from modules.memory.command_registry import find_command
            cmd = find_command(transcript)
            if cmd:
                spoken = cmd.get("response_text") or "On it, Boss."
                return ToolCall(
                    tool="run_custom_command",
                    args={"trigger": transcript},
                    spoken_response=spoken,
                    confidence=1.0,
                    safety=ActionSafety.SAFE,
                )
        except Exception as exc:
            logger.debug("Registry check failed: %s", exc)
        return None

    def warmup(self) -> None:
        """Load Ollama model into memory at startup so first command is fast."""
        try:
            logger.info("Warming up Ollama (%s)...", self._model)
            self._client.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": "hi", "stream": False, "options": {"num_predict": 1}},
                timeout=60,
            )
            logger.info("Ollama warm")
        except Exception as exc:
            logger.warning("Ollama warmup failed (will load on first command): %s", exc)

    def close(self) -> None:
        self._client.close()
