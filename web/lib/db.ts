import { neon } from "@neondatabase/serverless";

function sql() {
  return neon(process.env.DATABASE_URL!);
}

export async function initSchema() {
  const db = sql();
  await db`CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT,
    plan TEXT NOT NULL DEFAULT 'free', cmd_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`;
  await db`CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL, text TEXT NOT NULL, due_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`;
  await db`CREATE INDEX IF NOT EXISTS reminders_user_idx ON reminders(user_id)`;
  await db`CREATE TABLE IF NOT EXISTS shopping_items (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL, item TEXT NOT NULL, store TEXT, quantity TEXT,
    checked BOOLEAN NOT NULL DEFAULT false, added_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`;
  await db`CREATE INDEX IF NOT EXISTS shopping_user_idx ON shopping_items(user_id)`;
  await db`CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id TEXT NOT NULL, transcript TEXT NOT NULL, tool_called TEXT,
    response TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())`;
}

export async function createReminder(userId: string, text: string, dueAt?: string) {
  const rows = await sql()`INSERT INTO reminders (user_id, text, due_at)
    VALUES (${userId}, ${text}, ${dueAt ?? null}) RETURNING *`;
  return rows[0];
}

export async function getReminders(userId: string, scope = "upcoming") {
  const db = sql();
  if (scope === "today") {
    return db`SELECT * FROM reminders WHERE user_id = ${userId}
      AND status = 'pending' AND (due_at IS NULL OR due_at::date = CURRENT_DATE)
      ORDER BY due_at ASC NULLS LAST`;
  }
  return db`SELECT * FROM reminders WHERE user_id = ${userId} AND status = 'pending'
    ORDER BY due_at ASC NULLS LAST LIMIT 20`;
}

export async function completeReminder(userId: string, text: string) {
  return sql()`UPDATE reminders SET status = 'done'
    WHERE user_id = ${userId} AND status = 'pending' AND text ILIKE ${"%" + text + "%"}`;
}

export async function addShoppingItem(userId: string, item: string, store?: string, quantity?: string) {
  const rows = await sql()`INSERT INTO shopping_items (user_id, item, store, quantity)
    VALUES (${userId}, ${item}, ${store ?? null}, ${quantity ?? null}) RETURNING *`;
  return rows[0];
}

export async function getShoppingList(userId: string) {
  return sql()`SELECT * FROM shopping_items WHERE user_id = ${userId} AND checked = false
    ORDER BY added_at DESC`;
}

export async function checkShoppingItem(userId: string, item: string) {
  return sql()`UPDATE shopping_items SET checked = true
    WHERE user_id = ${userId} AND checked = false AND item ILIKE ${"%" + item + "%"}`;
}

export async function logInteraction(userId: string, transcript: string, tool: string, response: string) {
  await sql()`INSERT INTO interactions (user_id, transcript, tool_called, response)
    VALUES (${userId}, ${transcript}, ${tool}, ${response})`;
  await sql()`UPDATE users SET cmd_count = cmd_count + 1 WHERE id = ${userId}`;
}

export async function upsertUser(id: string, email: string, name: string) {
  const rows = await sql()`INSERT INTO users (id, email, name) VALUES (${id}, ${email}, ${name})
    ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, name = EXCLUDED.name RETURNING *`;
  return rows[0];
}

export async function getUser(id: string) {
  const rows = await sql()`SELECT * FROM users WHERE id = ${id}`;
  return rows[0] ?? null;
}
