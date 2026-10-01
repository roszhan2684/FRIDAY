"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Send, Loader2, Volume2, LayoutDashboard } from "lucide-react";
import Link from "next/link";

type Role = "user" | "friday";
type Status = "idle" | "listening" | "thinking" | "speaking";

interface Message {
  id: string;
  role: Role;
  text: string;
  timestamp: Date;
}

export default function AppPage() {
  const [messages, setMessages]   = useState<Message[]>([
    { id: "0", role: "friday", text: "Hey Boss! I'm FRIDAY — your AI assistant. Ask me anything: weather, reminders, web search, or just chat.", timestamp: new Date() }
  ]);
  const [input, setInput]         = useState("");
  const [status, setStatus]       = useState<Status>("idle");
  const [isRecording, setIsRecording] = useState(false);
  const bottomRef   = useRef<HTMLDivElement>(null);
  const mediaRef    = useRef<MediaRecorder | null>(null);
  const chunksRef   = useRef<Blob[]>([]);
  const synthRef    = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addMessage = useCallback((role: Role, text: string) => {
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role, text, timestamp: new Date() }]);
  }, []);

  const speak = useCallback((text: string) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 1.1;
    utt.pitch = 1.0;
    utt.onend = () => setStatus("idle");
    synthRef.current = utt;
    setStatus("speaking");
    window.speechSynthesis.speak(utt);
  }, []);

  const sendCommand = useCallback(async (text: string) => {
    if (!text.trim()) return;
    addMessage("user", text);
    setStatus("thinking");
    setInput("");
    try {
      const res  = await fetch("/api/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      const reply = data.spoken_response || data.output || "Done, Boss.";
      addMessage("friday", reply);
      // Open URL if tool returned one
      if (data.url) window.open(data.url, "_blank");
      speak(reply);
    } catch {
      const err = "Sorry Boss, something went wrong. Try again.";
      addMessage("friday", err);
      speak(err);
    }
  }, [addMessage, speak]);

  const startRecording = useCallback(async () => {
    if (isRecording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setStatus("thinking");
        try {
          const fd = new FormData();
          fd.append("audio", blob, "recording.webm");
          const res  = await fetch("/api/transcribe", { method: "POST", body: fd });
          const data = await res.json();
          if (data.text?.trim()) {
            await sendCommand(data.text);
          } else {
            setStatus("idle");
          }
        } catch {
          setStatus("idle");
        }
      };
      mr.start();
      mediaRef.current = mr;
      setIsRecording(true);
      setStatus("listening");
    } catch {
      alert("Microphone access is required for voice input.");
    }
  }, [isRecording, sendCommand]);

  const stopRecording = useCallback(() => {
    if (!isRecording || !mediaRef.current) return;
    mediaRef.current.stop();
    mediaRef.current = null;
    setIsRecording(false);
  }, [isRecording]);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    setStatus("idle");
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendCommand(input);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#06060f]">

      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">F</span>
          </div>
          <span className="font-bold gradient-text tracking-tight">FRIDAY</span>
          <StatusPill status={status} />
        </div>
        <div className="flex items-center gap-3">
          {status === "speaking" && (
            <button onClick={stopSpeaking} className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors">
              <Volume2 size={14} /> Stop
            </button>
          )}
          <Link href="/dashboard" className="text-slate-400 hover:text-white transition-colors">
            <LayoutDashboard size={18} />
          </Link>
        </div>
      </header>

      {/* ── Messages ────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        <AnimatePresence initial={false}>
          {messages.map(msg => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className={`flex gap-3 max-w-2xl mx-auto ${msg.role === "user" ? "flex-row-reverse" : ""}`}
            >
              <Avatar role={msg.role} />
              <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed max-w-md ${
                msg.role === "friday"
                  ? "bg-white/5 border border-white/8 text-slate-200 rounded-tl-sm"
                  : "bg-indigo-600 text-white rounded-tr-sm"
              }`}>
                {msg.text}
                <div className={`text-xs mt-1 ${msg.role === "friday" ? "text-slate-500" : "text-indigo-200"}`}>
                  {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            </motion.div>
          ))}

          {status === "thinking" && (
            <motion.div key="thinking" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3 max-w-2xl mx-auto">
              <Avatar role="friday" />
              <div className="px-4 py-4 rounded-2xl rounded-tl-sm bg-white/5 border border-white/8 flex items-center gap-1.5">
                <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ───────────────────────────────────────────────── */}
      <div className="shrink-0 px-4 pb-6 pt-3 border-t border-white/5">
        <div className="max-w-2xl mx-auto flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isRecording ? "Listening..." : "Ask FRIDAY anything..."}
              disabled={status === "thinking" || isRecording}
              rows={1}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pr-12 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:bg-white/7 transition-all"
              style={{ minHeight: "48px", maxHeight: "120px" }}
            />
            <button
              onClick={() => sendCommand(input)}
              disabled={!input.trim() || status === "thinking"}
              className="absolute right-3 bottom-3 text-slate-500 hover:text-indigo-400 disabled:opacity-30 transition-colors"
            >
              {status === "thinking" ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          </div>

          {/* Mic button */}
          <button
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onTouchStart={startRecording}
            onTouchEnd={stopRecording}
            disabled={status === "thinking"}
            className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 transition-all disabled:opacity-40 ${
              isRecording
                ? "bg-red-600 mic-glow scale-110"
                : "bg-indigo-600 hover:bg-indigo-500 hover:scale-105"
            }`}
          >
            {isRecording ? <MicOff size={18} className="text-white" /> : <Mic size={18} className="text-white" />}
          </button>
        </div>
        <p className="text-center text-xs text-slate-600 mt-3">
          Hold mic to speak · Press Enter to send
        </p>
      </div>
    </div>
  );
}

function Avatar({ role }: { role: Role }) {
  return (
    <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
      role === "friday" ? "bg-indigo-600 text-white" : "bg-slate-700 text-slate-300"
    }`}>
      {role === "friday" ? "F" : "U"}
    </div>
  );
}

function StatusPill({ status }: { status: Status }) {
  const labels: Record<Status, string> = {
    idle: "Ready", listening: "Listening…", thinking: "Thinking…", speaking: "Speaking…"
  };
  const colors: Record<Status, string> = {
    idle: "bg-emerald-500/15 text-emerald-400",
    listening: "bg-red-500/15 text-red-400",
    thinking: "bg-yellow-500/15 text-yellow-400",
    speaking: "bg-indigo-500/15 text-indigo-400",
  };
  return (
    <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${colors[status]}`}>
      {labels[status]}
    </span>
  );
}
