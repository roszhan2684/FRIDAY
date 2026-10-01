"use client";
import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Mic, ShoppingCart, Bell, LogOut, Plus, Check, Trash2 } from "lucide-react";
import { useClerk } from "@clerk/nextjs";

interface Reminder { id: string; text: string; due_at: string | null; status: string }
interface ShoppingItem { id: string; item: string; store: string | null; quantity: string | null; checked: boolean }

interface Props {
  user: { name: string; email: string };
  reminders: Reminder[];
  shopping: ShoppingItem[];
}

export default function DashboardClient({ user, reminders: initReminders, shopping: initShopping }: Props) {
  const { signOut } = useClerk();
  const [tab, setTab]           = useState<"reminders" | "shopping">("reminders");
  const [reminders, setReminders] = useState(initReminders);
  const [shopping, setShopping]   = useState(initShopping);

  const completeReminder = async (id: string, text: string) => {
    await fetch("/api/command", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: `I completed ${text}` }),
    });
    setReminders(r => r.filter(x => x.id !== id));
  };

  const checkItem = async (id: string, item: string) => {
    await fetch("/api/command", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: `I got the ${item}` }),
    });
    setShopping(s => s.filter(x => x.id !== id));
  };

  return (
    <div className="min-h-screen bg-[#06060f] text-slate-200">
      {/* ── Header ── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/5">
        <Link href="/app" className="flex items-center gap-2">
          <span className="font-bold gradient-text text-lg">FRIDAY</span>
        </Link>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-400 hidden sm:block">{user.email}</span>
          <Link href="/app" className="flex items-center gap-1.5 text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
            <Mic size={14} /> Open Assistant
          </Link>
          <button onClick={() => signOut()} className="text-slate-500 hover:text-slate-300 transition-colors">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-10">
        {/* ── Welcome ── */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mb-10">
          <h1 className="text-3xl font-bold mb-1">Hey, {user.name} 👋</h1>
          <p className="text-slate-400">Here's everything FRIDAY is tracking for you.</p>
        </motion.div>

        {/* ── Stats ── */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-10">
          <StatCard icon={Bell}         label="Active reminders" value={reminders.length} />
          <StatCard icon={ShoppingCart} label="Shopping items"    value={shopping.length} />
          <StatCard icon={Mic}          label="Commands today"    value="—" />
        </div>

        {/* ── Tabs ── */}
        <div className="flex gap-1 mb-6 p-1 bg-white/5 rounded-xl w-fit">
          {(["reminders", "shopping"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-5 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
                tab === t ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
              }`}>
              {t}
            </button>
          ))}
        </div>

        {/* ── Reminders ── */}
        {tab === "reminders" && (
          <div className="space-y-3">
            {reminders.length === 0 ? (
              <Empty text="No reminders. Say 'Hey FRIDAY, remind me to…' to add one." />
            ) : reminders.map((r, i) => (
              <motion.div key={r.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                className="glass rounded-xl px-5 py-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm text-white">{r.text}</p>
                  {r.due_at && <p className="text-xs text-slate-500 mt-0.5">{new Date(r.due_at).toLocaleString()}</p>}
                </div>
                <button onClick={() => completeReminder(r.id, r.text)}
                  className="w-8 h-8 rounded-lg bg-indigo-600/20 hover:bg-indigo-600 flex items-center justify-center transition-colors shrink-0">
                  <Check size={14} className="text-indigo-400" />
                </button>
              </motion.div>
            ))}
            <div className="flex justify-center pt-4">
              <Link href="/app" className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
                <Plus size={14} /> Add via voice
              </Link>
            </div>
          </div>
        )}

        {/* ── Shopping ── */}
        {tab === "shopping" && (
          <div className="space-y-3">
            {shopping.length === 0 ? (
              <Empty text="Shopping list is empty. Say 'Add milk to my shopping list' to get started." />
            ) : shopping.map((item, i) => (
              <motion.div key={item.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                className="glass rounded-xl px-5 py-4 flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm text-white">
                    {item.quantity && <span className="text-indigo-300 mr-1.5">{item.quantity}×</span>}
                    {item.item}
                  </p>
                  {item.store && <p className="text-xs text-slate-500 mt-0.5">from {item.store}</p>}
                </div>
                <button onClick={() => checkItem(item.id, item.item)}
                  className="w-8 h-8 rounded-lg bg-emerald-600/20 hover:bg-emerald-600 flex items-center justify-center transition-colors shrink-0">
                  <Trash2 size={14} className="text-emerald-400" />
                </button>
              </motion.div>
            ))}
            <div className="flex justify-center pt-4">
              <Link href="/app" className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
                <Plus size={14} /> Add via voice
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: number | string }) {
  return (
    <div className="glass rounded-xl p-5">
      <Icon size={18} className="text-indigo-400 mb-3" />
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="glass rounded-xl p-8 text-center text-slate-500 text-sm">
      {text}
    </div>
  );
}
