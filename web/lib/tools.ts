import {
  createReminder, getReminders, completeReminder,
  addShoppingItem, getShoppingList, checkShoppingItem,
} from "./db";

export interface ToolResult {
  output: string;
  spoken_response: string;
  url?: string;
}

// ── Weather ───────────────────────────────────────────────────────────────────

export async function get_weather(args: { location?: string }): Promise<ToolResult> {
  const loc = args.location || "auto";
  try {
    const res  = await fetch(`https://wttr.in/${encodeURIComponent(loc)}?format=j1`, {
      next: { revalidate: 1800 },
    });
    const data = await res.json();
    const cur  = data.current_condition[0];
    const area = data.nearest_area[0];
    const city = area.areaName[0].value;
    const temp = cur.temp_F;
    const desc = cur.weatherDesc[0].value;
    const feel = cur.FeelsLikeF;
    const text = `It's ${temp}°F and ${desc.toLowerCase()} in ${city}. Feels like ${feel}°F.`;
    return { output: text, spoken_response: text };
  } catch {
    return { output: "Couldn't fetch weather right now.", spoken_response: "Couldn't fetch the weather, Boss." };
  }
}

// ── Web search ────────────────────────────────────────────────────────────────

export async function search_web(args: { query: string }): Promise<ToolResult> {
  const url = `https://duckduckgo.com/?q=${encodeURIComponent(args.query)}&ia=web`;
  return {
    output: `Opening web search for: ${args.query}`,
    spoken_response: `Searching the web for ${args.query}, Boss.`,
    url,
  };
}

// ── YouTube ───────────────────────────────────────────────────────────────────

export async function search_youtube(args: { query: string }): Promise<ToolResult> {
  const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(args.query)}`;
  return {
    output: `Opening YouTube search for: ${args.query}`,
    spoken_response: `Searching YouTube for ${args.query}, Boss.`,
    url,
  };
}

// ── Open URL ──────────────────────────────────────────────────────────────────

export async function open_url(args: { url: string }): Promise<ToolResult> {
  const url = args.url.startsWith("http") ? args.url : `https://${args.url}`;
  const host = new URL(url).hostname.replace("www.", "");
  return {
    output: `Opening ${host}`,
    spoken_response: `Opening ${host}, Boss.`,
    url,
  };
}

// ── Reminders ─────────────────────────────────────────────────────────────────

export async function create_reminder(args: { text: string; due_at?: string }, userId: string): Promise<ToolResult> {
  await createReminder(userId, args.text, args.due_at);
  return {
    output: `Reminder saved: ${args.text}`,
    spoken_response: "Got it, Boss. Reminder saved.",
  };
}

export async function query_reminders(args: { scope?: string }, userId: string): Promise<ToolResult> {
  const rows = await getReminders(userId, args.scope || "upcoming");
  if (!rows.length) return { output: "No reminders.", spoken_response: "You have no reminders, Boss." };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const list = (rows as any[]).map((r) =>
    r.due_at ? `• ${r.text} (${new Date(r.due_at).toLocaleString()})` : `• ${r.text}`
  ).join("\n");
  return { output: list, spoken_response: `You have ${rows.length} reminder${rows.length > 1 ? "s" : ""}, Boss.` };
}

export async function complete_reminder(args: { text: string }, userId: string): Promise<ToolResult> {
  await completeReminder(userId, args.text);
  return { output: `Marked done: ${args.text}`, spoken_response: "Marked as done, Boss." };
}

// ── Shopping ──────────────────────────────────────────────────────────────────

export async function add_shopping_item(args: { item: string; store?: string; quantity?: string }, userId: string): Promise<ToolResult> {
  await addShoppingItem(userId, args.item, args.store, args.quantity);
  const qty  = args.quantity ? `${args.quantity} ` : "";
  const store = args.store ? ` from ${args.store}` : "";
  return {
    output: `Added: ${qty}${args.item}${store}`,
    spoken_response: `Added ${args.item} to your shopping list, Boss.`,
  };
}

export async function query_shopping_list(_args: Record<string, unknown>, userId: string): Promise<ToolResult> {
  const rows = await getShoppingList(userId);
  if (!rows.length) return { output: "Shopping list is empty.", spoken_response: "Your shopping list is empty, Boss." };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const list = (rows as any[]).map((r) => {
    const qty   = r.quantity ? `${r.quantity}× ` : "";
    const store = r.store ? ` (${r.store})` : "";
    return `• ${qty}${r.item}${store}`;
  }).join("\n");
  return { output: list, spoken_response: `You have ${rows.length} item${rows.length > 1 ? "s" : ""} on your list, Boss.` };
}

export async function check_shopping_item(args: { item: string }, userId: string): Promise<ToolResult> {
  await checkShoppingItem(userId, args.item);
  return { output: `Checked off: ${args.item}`, spoken_response: `Checked off ${args.item}, Boss.` };
}

// ── Briefing ──────────────────────────────────────────────────────────────────

export async function get_briefing(_args: Record<string, unknown>, userId: string): Promise<ToolResult> {
  const [weatherResult, reminders] = await Promise.all([
    get_weather({}),
    getReminders(userId, "today"),
  ]);
  const now  = new Date();
  const date = now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  let brief  = `Good ${getTimeOfDay()}, Boss. Today is ${date}.\n\n`;
  brief     += weatherResult.output + "\n\n";
  if (reminders.length) {
    brief += `Reminders today (${reminders.length}):\n`;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    brief += (reminders as any[]).map((r) => `• ${r.text}`).join("\n");
  } else {
    brief += "No reminders for today.";
  }
  return {
    output: brief,
    spoken_response: `Good ${getTimeOfDay()}, Boss. Here's your briefing.`,
  };
}

function getTimeOfDay() {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}

// ── Tool dispatcher ───────────────────────────────────────────────────────────

const REQUIRE_USER: Record<string, boolean> = {
  create_reminder: true, query_reminders: true, complete_reminder: true,
  add_shopping_item: true, query_shopping_list: true, check_shopping_item: true,
  get_briefing: true,
};

export async function dispatch(tool: string, args: Record<string, unknown>, userId: string): Promise<ToolResult> {
  switch (tool) {
    case "get_weather":         return get_weather(args as { location?: string });
    case "search_web":          return search_web(args as { query: string });
    case "search_youtube":      return search_youtube(args as { query: string });
    case "open_url":            return open_url(args as { url: string });
    case "create_reminder":     return create_reminder(args as { text: string; due_at?: string }, userId);
    case "query_reminders":     return query_reminders(args as { scope?: string }, userId);
    case "complete_reminder":   return complete_reminder(args as { text: string }, userId);
    case "add_shopping_item":   return add_shopping_item(args as { item: string; store?: string; quantity?: string }, userId);
    case "query_shopping_list": return query_shopping_list(args, userId);
    case "check_shopping_item": return check_shopping_item(args as { item: string }, userId);
    case "get_briefing":        return get_briefing(args, userId);
    case "respond_only": {
      const msg = (args.message as string) || "I'm here, Boss.";
      return { output: msg, spoken_response: msg };
    }
    default:
      return { output: "I don't know how to do that yet.", spoken_response: "I can't do that yet, Boss." };
  }
}

export { REQUIRE_USER };
