import Groq from "groq-sdk";

function getGroq() {
  return new Groq({ apiKey: process.env.GROQ_API_KEY ?? "placeholder" });
}

const SYSTEM = `You are FRIDAY, a smart AI voice assistant. Parse the user's command into a JSON tool call.

AVAILABLE TOOLS:
- get_weather       — args: { location?: string }
- search_web        — args: { query: string }
- search_youtube    — args: { query: string }
- open_url          — args: { url: string }
- create_reminder   — args: { text: string, due_at?: string (ISO8601) }
- query_reminders   — args: { scope?: "today"|"upcoming" }
- complete_reminder — args: { text: string }
- add_shopping_item — args: { item: string, store?: string, quantity?: string }
- query_shopping_list — args: {}
- check_shopping_item — args: { item: string }
- get_briefing      — args: {}
- respond_only      — args: { message: string }

RULES:
1. Output ONLY valid JSON. No markdown, no explanation.
2. spoken_response must be short (under 12 words), address user as "Boss".
3. Use respond_only for questions you can answer directly (time, date, general knowledge).
4. For time/date questions: include the answer in args.message.

OUTPUT FORMAT:
{"tool": "<name>", "args": {...}, "spoken_response": "<short reply>"}`;

const FEW_SHOT = [
  { role: "user" as const,      content: "what's the weather" },
  { role: "assistant" as const, content: '{"tool":"get_weather","args":{},"spoken_response":"Checking the weather, Boss."}' },
  { role: "user" as const,      content: "remind me to call mom tonight" },
  { role: "assistant" as const, content: '{"tool":"create_reminder","args":{"text":"call mom tonight"},"spoken_response":"Saved, Boss."}' },
  { role: "user" as const,      content: "add milk to shopping list" },
  { role: "assistant" as const, content: '{"tool":"add_shopping_item","args":{"item":"milk"},"spoken_response":"Added milk, Boss."}' },
  { role: "user" as const,      content: "search youtube for lo fi beats" },
  { role: "assistant" as const, content: '{"tool":"search_youtube","args":{"query":"lo fi beats"},"spoken_response":"Searching YouTube, Boss."}' },
  { role: "user" as const,      content: "open netflix" },
  { role: "assistant" as const, content: '{"tool":"open_url","args":{"url":"https://netflix.com"},"spoken_response":"Opening Netflix, Boss."}' },
  { role: "user" as const,      content: "give me a briefing" },
  { role: "assistant" as const, content: '{"tool":"get_briefing","args":{},"spoken_response":"Here is your briefing, Boss."}' },
];

// ── Pre-filter: instant rules before hitting Groq ─────────────────────────────

function preFilter(t: string): { tool: string; args: Record<string, unknown>; spoken_response: string } | null {
  const lower = t.toLowerCase().trim();

  // Date / time
  if (/what('?s| is) (today|the date|day)/.test(lower) || /what time/.test(lower)) {
    const now  = new Date();
    const date = now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
    const time = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
    const msg  = `Today is ${date}. The time is ${time}.`;
    return { tool: "respond_only", args: { message: msg }, spoken_response: msg };
  }

  // Weather
  if (/weather|temperature|forecast|how hot|how cold|raining/.test(lower)) {
    const locM = lower.match(/weather (?:in|for|at) (.+)$/);
    return { tool: "get_weather", args: locM ? { location: locM[1] } : {}, spoken_response: "Checking the weather, Boss." };
  }

  // Streaming
  const streams: Record<string, string> = {
    netflix: "https://netflix.com", hulu: "https://hulu.com",
    "disney plus": "https://disneyplus.com", "disney+": "https://disneyplus.com",
    "apple tv": "https://tv.apple.com", "prime video": "https://primevideo.com",
    "amazon prime": "https://primevideo.com", twitch: "https://twitch.tv",
    crunchyroll: "https://crunchyroll.com",
  };
  for (const [kw, url] of Object.entries(streams)) {
    if (lower.includes(kw) && /open|watch|play|launch|go to/.test(lower)) {
      return { tool: "open_url", args: { url }, spoken_response: `Opening ${kw}, Boss.` };
    }
  }

  // Briefing
  if (/briefing|brief me|morning update|what('?s| is) going on/.test(lower))
    return { tool: "get_briefing", args: {}, spoken_response: "Here is your briefing, Boss." };

  // Remind me
  if (/\bremind me\b/.test(lower))
    return { tool: "create_reminder", args: { text: t }, spoken_response: "Got it, Boss. Reminder saved." };

  // Shopping
  if (/add .+ to (my )?(shopping|grocery) list/.test(lower)) {
    const item = lower.replace(/add (.+) to (my )?(shopping|grocery) list.*/, "$1").trim();
    return { tool: "add_shopping_item", args: { item }, spoken_response: `Added ${item}, Boss.` };
  }
  if (/(what('?s| is) on|show|read) (my )?(shopping|grocery) list/.test(lower))
    return { tool: "query_shopping_list", args: {}, spoken_response: "Here is your shopping list, Boss." };

  // My reminders
  if (/(what are|show|list) my reminders/.test(lower))
    return { tool: "query_reminders", args: { scope: "today" }, spoken_response: "Here are your reminders, Boss." };

  return null;
}

// ── Main planner ──────────────────────────────────────────────────────────────

export interface PlanResult {
  tool: string;
  args: Record<string, unknown>;
  spoken_response: string;
}

export async function plan(transcript: string): Promise<PlanResult> {
  // Try pre-filter first (no LLM cost)
  const pre = preFilter(transcript);
  if (pre) return pre;

  // Fall back to Groq
  try {
    const completion = await getGroq().chat.completions.create({
      model: "llama-3.1-8b-instant",
      messages: [
        { role: "system", content: SYSTEM },
        ...FEW_SHOT,
        { role: "user", content: transcript },
      ],
      temperature: 0.05,
      max_tokens: 120,
      response_format: { type: "json_object" },
    });

    const raw  = completion.choices[0]?.message?.content ?? "{}";
    const data = JSON.parse(raw);
    return {
      tool:             data.tool            || "respond_only",
      args:             data.args            || {},
      spoken_response:  data.spoken_response || "Done, Boss.",
    };
  } catch {
    return { tool: "respond_only", args: { message: "Sorry Boss, I had trouble understanding that." }, spoken_response: "Sorry Boss, try again." };
  }
}
