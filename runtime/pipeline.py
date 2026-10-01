"""Main orchestration pipeline — routes audio/text through all modules.

Lifecycle:
  start() → launches wake word loop in background thread
  on_wake(audio_preroll) → captures command audio → runs full pipeline
  handle_typed_command(text) → skips wake/STT → runs plan + execute
"""
from __future__ import annotations
import asyncio
import logging
import queue
import threading
import time
import uuid
from typing import Callable, Awaitable

import numpy as np

from modules.wake.detector import WakeWordDetector
from modules.stt.transcriber import Transcriber
from modules.llm.planner import Planner
from modules.tts.speaker import Speaker
from modules.automation.mac_actions import MacActionExecutor
from modules.memory.store import (
    log_interaction,
    get_all_aliases,
    get_recent_transcripts,
    audit,
)
from modules.memory.learner import Learner
from shared.schemas import (
    Transcript,
    ToolCall,
    InteractionEvent,
    CommandResponse,
    ActionSafety,
    OutcomeStatus,
    PipelineState,
)
from shared.events import (
    RuntimeEvent,
    state_event,
    transcript_event,
    action_event,
    result_event,
    confirm_event,
)
from shared.constants import (
    AUDIO_SAMPLE_RATE,
    AUDIO_CHUNK_FRAMES,
    SILENCE_THRESHOLD_SECONDS,
    MAX_CAPTURE_SECONDS,
)
from runtime.config import settings

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self):
        self.state: str = PipelineState.IDLE.value
        self._session_id = str(uuid.uuid4())
        self._broadcast: Callable[[RuntimeEvent], Awaitable[None]] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        self._wake = WakeWordDetector(
            model_path=settings.wake_model_path,
            threshold=settings.wake_threshold,
        )
        self._stt = Transcriber(model_id=settings.whisper_model, language=settings.whisper_language)
        self._planner = Planner(model=settings.ollama_model, base_url=settings.ollama_base_url)
        self._speaker = Speaker(
            voice=settings.tts_voice,
            rate=settings.tts_rate,
            murf_api_key=settings.murf_api_key,
            murf_voice_id=settings.murf_voice_id,
            murf_style=settings.murf_style,
        )
        self._executor = MacActionExecutor()
        self._learner = Learner()

        self._pending_tool_call: ToolCall | None = None
        self._last_tool: str | None = None
        self._last_args: dict = {}
        self._awaiting_followup: str | None = None
        self._setup_session = None
        # Stop word: when True, FRIDAY ignores all audio until wake word re-detected
        self._stopped: bool = False

        from modules.automation.proactive_watcher import ProactiveWatcher
        self._watcher = ProactiveWatcher()

        # Backend sync client (Phase 0 cloud — gracefully disabled if not configured)
        from runtime.backend_sync import BackendSyncClient
        self._backend_sync = BackendSyncClient(
            backend_url=settings.backend_url,
            api_key=settings.backend_key,
        )

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        await asyncio.get_event_loop().run_in_executor(None, self._stt.load)
        logger.info("STT model loaded")
        # Warm up Ollama so first command doesn't pay model-load latency
        await asyncio.get_event_loop().run_in_executor(None, self._planner.warmup)
        self._wake.set_callback(self._on_wake)
        self._wake.start()
        # Start proactive watcher (fires reminders + meeting alerts)
        self._watcher.start(speak_callback=self._speaker.speak, loop=self._loop)
        # Start background cloud sync
        self._backend_sync.start()
        self._set_state(PipelineState.LISTENING_FOR_WAKE)
        logger.info("FRIDAY pipeline started — listening for wake word")

    async def stop(self) -> None:
        self._wake.stop()
        self._watcher.stop()
        self._backend_sync.stop()
        self._planner.close()
        logger.info("Pipeline stopped")

    def set_broadcast(self, broadcast_fn: Callable[[RuntimeEvent], Awaitable[None]]) -> None:
        self._broadcast = broadcast_fn

    # ─── Wake Handler ─────────────────────────────────────────────────────────

    # ─── Stop word ─────────────────────────────────────────────────────────────

    STOP_WORDS = frozenset({
        "stop", "stop listening", "go away", "quiet", "silence",
        "that's enough", "thats enough", "pause", "mute",
        "friday stop", "hey friday stop",
    })

    def _is_stop_word(self, text: str) -> bool:
        return text.lower().strip() in self.STOP_WORDS

    _WAKE_PREFIXES = (
        "hey friday ", "hey friday, ", "friday ", "friday, ",
        "ok friday ", "okay friday ",
    )

    def _strip_wake_phrase(self, text: str) -> str:
        """Remove wake phrase from start of transcript (STT sometimes captures it)."""
        lower = text.lower().strip()
        for prefix in self._WAKE_PREFIXES:
            if lower.startswith(prefix):
                return text[len(prefix):].strip()
        return text.strip()

    def _on_wake(self, preroll_audio: bytes) -> None:
        """Called from wake detector thread. Captures audio then dispatches to async pipeline."""
        # Wake word re-activates FRIDAY even if stopped
        self._stopped = False

        if self.state != PipelineState.LISTENING_FOR_WAKE.value:
            return

        self._set_state(PipelineState.CAPTURING)
        self._speaker.speak("Yes, Boss?", blocking=False)

        # Don't pass preroll — it's the wake phrase itself, not the command
        command_audio = self._capture_command(None)
        if not command_audio:
            self._set_state(PipelineState.LISTENING_FOR_WAKE)
            return

        self._set_state(PipelineState.TRANSCRIBING)
        transcript = self._stt.transcribe(command_audio)
        self._emit(transcript_event(
            transcript.text,
            transcript.confidence,
            transcript.confidence < settings.confidence_threshold,
        ))

        clean_text = self._strip_wake_phrase(transcript.text)
        transcript = Transcript(
            text=clean_text,
            confidence=transcript.confidence,
            audio_hash=transcript.audio_hash,
            duration_seconds=transcript.duration_seconds,
            model=transcript.model,
        )

        if not clean_text.strip() or len(clean_text.split()) < 2:
            self._set_state(PipelineState.LISTENING_FOR_WAKE)
            return

        if self._is_stop_word(transcript.text):
            self._stopped = True
            self._speaker.stop()
            self._speaker.speak("Going silent, Boss. Say 'Hey Friday' when you need me.", blocking=False)
            self._set_state(PipelineState.IDLE)
            return

        if transcript.confidence < settings.confidence_threshold:
            logger.info("Low confidence (%.2f) — awaiting typed correction", transcript.confidence)
            self._set_state(PipelineState.IDLE)
            return

        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._run_plan_execute(transcript.text, transcript),
                self._loop,
            )

    # ─── Core Pipeline ────────────────────────────────────────────────────────

    async def _run_plan_execute(
        self, text: str, transcript: Transcript | None = None
    ) -> CommandResponse:
        # ── Stop word check — go silent until next wake word ─────────────────
        if self._is_stop_word(text):
            self._stopped = True
            self._speaker.stop()
            self._speaker.speak("Going silent, Boss. Say 'Hey Friday' when you need me.", blocking=False)
            self._set_state(PipelineState.IDLE)
            return CommandResponse(
                transcript=text, tool_called="respond_only",
                spoken_response="Going silent, Boss.", success=True, output="Stop word received."
            )

        if self._stopped:
            # Silently ignore — not listening until wake word
            return CommandResponse(
                transcript=text, tool_called="respond_only",
                spoken_response="", success=True, output="[silenced]"
            )

        # ── Setup conversation: if a SetupSession is active, feed input ────────
        if self._setup_session is not None:
            return await self._handle_setup_input(text, transcript)

        # ── Multi-turn: if FRIDAY is waiting for a follow-up, resolve it first ──
        if self._awaiting_followup:
            followup_response = await self._resolve_followup(text, transcript)
            if followup_response:
                return followup_response

        start = time.monotonic()
        self._set_state(PipelineState.PLANNING)

        aliases = get_all_aliases()
        recent = get_recent_transcripts(limit=10)
        plan = self._planner.plan(text, aliases=aliases, recent_commands=recent)
        tool_call = plan.tool_call

        self._emit(action_event(tool_call.tool, tool_call.spoken_response))

        if tool_call.safety == ActionSafety.CONFIRM and settings.confirm_risky_actions:
            self._pending_tool_call = tool_call
            self._set_state(PipelineState.CONFIRMING)
            self._emit(confirm_event(tool_call.tool, tool_call.args, tool_call.spoken_response))
            self._speaker.speak("Boss, this action needs your confirmation.")
            return CommandResponse(
                transcript=text,
                tool_called=tool_call.tool,
                spoken_response=tool_call.spoken_response,
                success=True,
                output="Awaiting confirmation",
            )

        if tool_call.safety == ActionSafety.BLOCKED:
            self._speaker.speak("I can't do that, Boss.")
            self._set_state(PipelineState.LISTENING_FOR_WAKE)
            return CommandResponse(
                transcript=text,
                tool_called=tool_call.tool,
                spoken_response="I can't do that, Boss.",
                success=False,
                error="Action is blocked.",
            )

        return await self._execute_and_respond(tool_call, text, transcript, start)

    async def _execute_and_respond(
        self,
        tool_call: ToolCall,
        transcript_text: str,
        transcript: Transcript | None,
        start: float,
    ) -> CommandResponse:
        self._set_state(PipelineState.EXECUTING)
        audit(f"execute:{tool_call.tool}", tool_call.tool, tool_call.args)

        result = self._executor.execute(tool_call)
        duration_ms = int((time.monotonic() - start) * 1000)

        self._emit(result_event(result.success, result.output, result.error))

        if result.success:
            self._set_state(PipelineState.SPEAKING)
            self._speaker.speak(tool_call.spoken_response)
        else:
            self._speaker.speak(f"That didn't work, Boss. {result.error or ''}")

        # ── Track last action for multi-turn follow-up prompts ──
        self._last_tool = tool_call.tool
        self._last_args = tool_call.args

        outcome = OutcomeStatus.SUCCESS if result.success else OutcomeStatus.FAILED
        event = InteractionEvent(
            session_id=self._session_id,
            transcript=transcript_text,
            audio_hash=transcript.audio_hash if transcript else None,
            confidence=transcript.confidence if transcript else None,
            tool_called=tool_call.tool,
            tool_args=tool_call.args,
            spoken_response=tool_call.spoken_response,
            outcome=outcome,
            error=result.error,
            duration_ms=duration_ms,
            metadata=result.metadata,
        )
        log_interaction(event)

        if settings.learning_enabled:
            self._learner.update_from_interaction(event)

        # ── Offer to set up a custom command if respond_only on an intent phrase ──
        if self._should_offer_setup(transcript_text, tool_call.tool) and result.success:
            await asyncio.sleep(0.8)
            offer = f"Boss, I don't have that saved yet. Want me to set it up so I remember next time?"
            self._speaker.speak(offer, blocking=False)
            self._awaiting_followup = f"SETUP:{transcript_text}"
            self._set_state(PipelineState.LISTENING_FOR_WAKE)
            return CommandResponse(
                transcript=transcript_text, tool_called=tool_call.tool,
                spoken_response=offer, success=True, output="Offering setup."
            )

        # ── Generate follow-up prompt if this action warrants one ──
        followup = self._maybe_ask_followup(tool_call.tool, tool_call.args, result)
        if followup and result.success:
            await asyncio.sleep(1.5)
            self._speaker.speak(followup, blocking=False)
            self._awaiting_followup = f"{tool_call.tool}:{list(tool_call.args.values())[:1]}"
            self._set_state(PipelineState.LISTENING_FOR_WAKE)
        else:
            self._awaiting_followup = None
            self._set_state(PipelineState.LISTENING_FOR_WAKE)

        return CommandResponse(
            transcript=transcript_text,
            tool_called=tool_call.tool,
            spoken_response=tool_call.spoken_response,
            success=result.success,
            output=result.output,
            error=result.error,
        )

    # ─── Public API ───────────────────────────────────────────────────────────

    async def handle_typed_command(self, text: str) -> CommandResponse:
        # Typed commands from the UI always bypass the silence state
        # (silence only applies to the voice microphone path)
        self._stopped = False
        try:
            return await self._run_plan_execute(text, transcript=None)
        except Exception as exc:
            logger.exception("handle_typed_command failed: %s", exc)
            return CommandResponse(
                transcript=text,
                tool_called="error",
                spoken_response="",
                success=False,
                error=str(exc),
            )

    async def handle_correction(
        self, bad_transcript: str, corrected_text: str, audio_hash: str = ""
    ) -> CommandResponse:
        self._learner.ingest_correction(audio_hash, bad_transcript, corrected_text)
        return await self._run_plan_execute(corrected_text, transcript=None)

    async def handle_confirmation(self, confirmed: bool) -> None:
        if not self._pending_tool_call:
            return
        tc = self._pending_tool_call
        self._pending_tool_call = None
        if confirmed:
            audit(f"confirmed:{tc.tool}", tc.tool, tc.args, confirmed=True)
            await self._execute_and_respond(tc, tc.spoken_response, None, time.monotonic())
        else:
            self._speaker.speak("Cancelled, Boss.")
            self._set_state(PipelineState.LISTENING_FOR_WAKE)

    # ─── Audio Capture ────────────────────────────────────────────────────────

    def _capture_command(self, preroll: bytes) -> bytes | None:
        """Record audio until silence or max duration. Uses sounddevice."""
        try:
            import sounddevice as sd  # type: ignore
        except ImportError:
            logger.error("sounddevice not installed — cannot capture audio.")
            return None

        frames: list[np.ndarray] = []
        if preroll:
            frames.append(np.frombuffer(preroll, dtype=np.int16))

        silence_chunks = 0
        max_chunks = int(MAX_CAPTURE_SECONDS * AUDIO_SAMPLE_RATE / AUDIO_CHUNK_FRAMES)
        silence_limit = int(SILENCE_THRESHOLD_SECONDS * AUDIO_SAMPLE_RATE / AUDIO_CHUNK_FRAMES)
        rms_threshold = 300
        audio_q: "queue.Queue[np.ndarray]" = queue.Queue()

        def cb(indata: np.ndarray, _frames: int, _time, _status) -> None:
            audio_q.put(indata[:, 0].copy())

        try:
            stream = sd.InputStream(
                samplerate=AUDIO_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=AUDIO_CHUNK_FRAMES,
                callback=cb,
            )
        except Exception as exc:
            logger.error("Could not open microphone: %s", exc)
            return None

        with stream:
            for _ in range(max_chunks):
                try:
                    chunk = audio_q.get(timeout=1.0)
                except Exception:
                    break
                frames.append(chunk)
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                if rms < rms_threshold:
                    silence_chunks += 1
                    if silence_chunks >= silence_limit:
                        break
                else:
                    silence_chunks = 0

        if not frames:
            return None
        return np.concatenate(frames).tobytes()

    # ─── Utilities ────────────────────────────────────────────────────────────

    def _set_state(self, state: PipelineState) -> None:
        self.state = state.value
        self._emit(state_event(state.value))

    # ─── Setup conversation ───────────────────────────────────────────────────

    def _start_setup_session(self, trigger_phrase: str) -> str:
        """Begin a guided setup conversation for a new custom command."""
        from modules.memory.command_registry import SetupSession
        from modules.automation.chrome_profiles import get_cached_profiles, discover_profiles
        self._setup_session = SetupSession(trigger_phrase)
        # Ensure Chrome profiles are cached
        if not get_cached_profiles():
            discover_profiles()
        question = self._setup_session.next_question(get_cached_profiles())
        return question

    async def _handle_setup_input(self, text: str, transcript) -> CommandResponse:
        """Feed user input into the active SetupSession and advance state."""
        from modules.memory.command_registry import save_command, get_cached_profiles

        session = self._setup_session
        t = text.lower().strip()

        # User cancels setup
        if t in ("cancel", "stop", "never mind", "nevermind", "quit", "exit"):
            self._setup_session = None
            spoken = "Setup cancelled, Boss."
            self._speaker.speak(spoken)
            self._set_state(PipelineState.LISTENING_FOR_WAKE)
            return CommandResponse(
                transcript=text, tool_called="respond_only",
                spoken_response=spoken, success=True, output="Setup cancelled."
            )

        session.feed(text)

        if session.is_done:
            # Save the command and run it immediately
            args = session.to_save_args()
            save_command(**args)
            self._setup_session = None
            spoken = f"Saved, Boss. Running it now."
            self._speaker.speak(spoken)

            # Execute the newly saved command
            from shared.schemas import ToolCall, ActionSafety
            tc = ToolCall(
                tool="run_custom_command",
                args={"trigger": session.trigger_phrase},
                spoken_response=args["response_text"],
                confidence=1.0,
                safety=ActionSafety.SAFE,
            )
            return await self._execute_and_respond(tc, text, transcript, time.monotonic())
        else:
            # Ask the next question
            question = session.next_question(get_cached_profiles())
            self._speaker.speak(question)
            self._set_state(PipelineState.LISTENING_FOR_WAKE)
            return CommandResponse(
                transcript=text, tool_called="respond_only",
                spoken_response=question, success=True, output=f"Setup step: {session.step}"
            )

    def _should_offer_setup(self, transcript: str, tool_called: str) -> bool:
        """
        Return True if FRIDAY should offer to set up a new custom command.
        Triggered when: respond_only is the result AND the transcript sounds like
        a personal intent ("I want to X", "open my X", "start X mode").
        """
        t = transcript.lower()
        intent_signals = [
            "i want to", "i need to", "i'd like to", "let me",
            "open my", "start my", "set up", "apply for", "watch a", "study",
        ]
        return tool_called == "respond_only" and any(s in t for s in intent_signals)

    # ─── Multi-turn conversation helpers ──────────────────────────────────────

    def _maybe_ask_followup(self, tool: str, args: dict, result) -> str | None:
        """Return a follow-up prompt string if this action warrants one."""
        url = args.get("url", "")
        name = args.get("name", "")

        if tool == "open_url" and "youtube.com" in url and "results" not in url:
            return "Want me to search for something on YouTube, Boss?"
        if tool == "open_app" and name.lower() == "youtube":
            return "Want me to search for something on YouTube, Boss?"
        if tool == "open_file" and result.success:
            return None  # Don't ask follow-up for file opens — too noisy
        if tool == "open_url" and "netflix.com" in url:
            return "Want me to look up what to watch tonight, Boss?"
        return None

    async def _resolve_followup(
        self, text: str, transcript: Transcript | None
    ) -> CommandResponse | None:
        """Handle a reply to a pending follow-up question."""
        context = self._awaiting_followup
        self._awaiting_followup = None

        t = text.lower().strip()
        no_words = {"no", "nope", "nah", "never mind", "nevermind", "cancel", "skip", "nothing"}

        # Setup offer follow-up
        if context and context.startswith("SETUP:"):
            trigger_phrase = context[6:]
            yes_words = {"yes", "yeah", "yep", "sure", "ok", "okay", "do it", "set it up"}
            if any(w in t for w in yes_words):
                question = self._start_setup_session(trigger_phrase)
                self._speaker.speak(question)
                self._set_state(PipelineState.LISTENING_FOR_WAKE)
                return CommandResponse(
                    transcript=text, tool_called="respond_only",
                    spoken_response=question, success=True,
                    output=f"Starting setup for: {trigger_phrase}"
                )
            else:
                self._speaker.speak("No problem, Boss.")
                self._set_state(PipelineState.LISTENING_FOR_WAKE)
                return CommandResponse(
                    transcript=text, tool_called="respond_only",
                    spoken_response="No problem, Boss.", success=True, output="Setup skipped."
                )

        if any(w in t for w in no_words):
            self._speaker.speak("Got it, Boss.")
            self._set_state(PipelineState.LISTENING_FOR_WAKE)
            return CommandResponse(
                transcript=text, tool_called="respond_only",
                spoken_response="Got it, Boss.", success=True, output="Follow-up cancelled."
            )

        # YouTube follow-up → search YouTube
        if context and "open_url" in context and "youtube" in context.lower():
            from shared.schemas import ToolCall, ActionSafety
            tc = ToolCall(
                tool="search_youtube", args={"query": text},
                spoken_response=f"Searching YouTube for {text}, Boss.",
                confidence=0.95, safety=ActionSafety.SAFE,
            )
            start = time.monotonic()
            return await self._execute_and_respond(tc, text, transcript, start)

        # Netflix/movie follow-up → lookup_movie
        if context and "netflix" in context.lower():
            from shared.schemas import ToolCall, ActionSafety
            tc = ToolCall(
                tool="lookup_movie", args={"title": text},
                spoken_response=f"Looking up {text} for you, Boss.",
                confidence=0.9, safety=ActionSafety.SAFE,
            )
            start = time.monotonic()
            return await self._execute_and_respond(tc, text, transcript, start)

        # Unknown follow-up context — just process normally
        return None

    def _emit(self, event: RuntimeEvent) -> None:
        if self._broadcast and self._loop:
            asyncio.run_coroutine_threadsafe(self._broadcast(event), self._loop)
