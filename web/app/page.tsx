"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Mic, Zap, Brain, Calendar, ShoppingCart,
  Cloud, Search, ChevronRight, Check, Star
} from "lucide-react";

const features = [
  { icon: Mic,          title: "Voice-First",          desc: "Just speak. FRIDAY listens, understands, and responds in natural language." },
  { icon: Brain,        title: "AI-Powered",            desc: "Groq-accelerated LLM with sub-second planning for every command." },
  { icon: Calendar,     title: "Reminders & Schedule",  desc: "Create, snooze, and query reminders entirely by voice." },
  { icon: ShoppingCart, title: "Shopping Lists",         desc: "Add items hands-free. Check them off when you're done." },
  { icon: Cloud,        title: "Live Weather",           desc: "Instant weather for any city, any time, without opening an app." },
  { icon: Search,       title: "Web & YouTube Search",   desc: "Search the web or find YouTube videos by saying what you want." },
];

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Perfect for trying FRIDAY out.",
    features: [
      "50 voice commands / month",
      "Reminders & shopping list",
      "Weather & web search",
      "Browser TTS voice",
    ],
    cta: "Get Started",
    href: "/sign-up",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$9",
    period: "/ month",
    description: "For power users who want it all.",
    features: [
      "Unlimited voice commands",
      "High-quality neural TTS voice",
      "Priority Groq inference",
      "Full conversation history",
      "YouTube & web search",
      "Early access to new features",
    ],
    cta: "Start Free Trial",
    href: "/sign-up?plan=pro",
    highlighted: true,
  },
];

const faqs = [
  { q: "Do I need to install anything?", a: "No. FRIDAY runs entirely in your browser. Click the mic and start talking." },
  { q: "What LLM powers FRIDAY?",        a: "Groq-accelerated Llama 3.1. Responses arrive in under 2 seconds." },
  { q: "Is my voice data stored?",        a: "Audio is transcribed on the fly and never stored. Only the transcript is saved." },
  { q: "Can I cancel anytime?",           a: "Yes. Cancel from your account settings with one click. No questions asked." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#06060f] text-slate-200 overflow-x-hidden">

      {/* ── Nav ───────────────────────────────────────────────────── */}
      <nav className="fixed top-0 inset-x-0 z-50 flex items-center justify-between px-6 py-4 border-b border-white/5 backdrop-blur bg-[#06060f]/80">
        <span className="text-xl font-bold gradient-text tracking-tight">FRIDAY</span>
        <div className="flex items-center gap-4">
          <Link href="#pricing" className="text-sm text-slate-400 hover:text-white transition-colors hidden sm:block">Pricing</Link>
          <Link href="/sign-in" className="text-sm text-slate-400 hover:text-white transition-colors">Sign in</Link>
          <Link href="/sign-up" className="text-sm bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium transition-colors">
            Get Started
          </Link>
        </div>
      </nav>

      {/* ── Hero ──────────────────────────────────────────────────── */}
      <section className="relative flex flex-col items-center justify-center min-h-screen px-6 text-center pt-20">
        {/* Background glow */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-indigo-600/10 blur-[120px]" />
          <div className="absolute top-1/2 left-1/4 w-[400px] h-[400px] rounded-full bg-violet-600/8 blur-[100px]" />
        </div>

        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 text-sm font-medium mb-8">
            <Zap size={14} className="text-indigo-400" />
            Powered by Groq · Sub-2s responses
          </div>

          <h1 className="text-5xl sm:text-7xl font-bold tracking-tight mb-6 leading-none">
            Your AI assistant,<br />
            <span className="gradient-text">activated by voice</span>
          </h1>

          <p className="text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            FRIDAY listens, thinks, and acts. Manage reminders, search the web,
            check the weather — all without touching a keyboard.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/sign-up" className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-8 py-4 rounded-xl font-semibold text-lg transition-all hover:scale-105 hover:shadow-lg hover:shadow-indigo-500/25">
              <Mic size={20} />
              Start talking — it&apos;s free
            </Link>
            <Link href="#features" className="inline-flex items-center gap-2 border border-white/10 hover:border-white/20 text-slate-300 px-8 py-4 rounded-xl font-semibold text-lg transition-all hover:bg-white/5">
              See how it works <ChevronRight size={18} />
            </Link>
          </div>
        </motion.div>

        {/* Mock UI */}
        <motion.div
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="mt-20 w-full max-w-2xl"
        >
          <div className="glass rounded-2xl p-6 text-left">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-3 h-3 rounded-full bg-red-500/60" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
              <div className="w-3 h-3 rounded-full bg-green-500/60" />
              <span className="ml-2 text-xs text-slate-500 font-mono">friday.ai/app</span>
            </div>
            <div className="space-y-4">
              <ChatBubble side="user" text="Hey Friday, what's the weather today?" />
              <ChatBubble side="friday" text="It's 72°F and sunny in Fullerton right now, Boss. Perfect day to work outside." />
              <ChatBubble side="user" text="Remind me to call the dentist at 3 PM." />
              <ChatBubble side="friday" text="Done, Boss. Reminding you to call the dentist at 3:00 PM." />
            </div>
            <div className="mt-5 flex items-center gap-3">
              <div className="flex-1 h-11 rounded-xl bg-white/5 border border-white/10 flex items-center px-4 text-slate-500 text-sm">
                Say something or type a command...
              </div>
              <div className="w-11 h-11 rounded-xl bg-indigo-600 flex items-center justify-center">
                <Mic size={18} className="text-white" />
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ── Features ──────────────────────────────────────────────── */}
      <section id="features" className="py-32 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">Everything you need. Nothing you don&apos;t.</h2>
            <p className="text-slate-400 text-lg max-w-xl mx-auto">
              Built for speed. Designed to disappear — you talk, it works.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="glass rounded-2xl p-6 hover:border-indigo-500/30 transition-colors group"
              >
                <div className="w-10 h-10 rounded-xl bg-indigo-500/15 flex items-center justify-center mb-4 group-hover:bg-indigo-500/25 transition-colors">
                  <f.icon size={20} className="text-indigo-400" />
                </div>
                <h3 className="font-semibold text-white mb-2">{f.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ───────────────────────────────────────────────── */}
      <section id="pricing" className="py-32 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">Simple, honest pricing</h2>
            <p className="text-slate-400 text-lg">Start free. Upgrade when you&apos;re ready.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {plans.map((plan) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className={`rounded-2xl p-8 flex flex-col ${
                  plan.highlighted
                    ? "bg-indigo-600 border border-indigo-500"
                    : "glass"
                }`}
              >
                {plan.highlighted && (
                  <div className="flex items-center gap-1.5 text-indigo-200 text-xs font-semibold uppercase tracking-wider mb-4">
                    <Star size={12} fill="currentColor" /> Most Popular
                  </div>
                )}
                <div className="mb-2">
                  <span className="text-4xl font-bold">{plan.price}</span>
                  <span className={`ml-1 text-sm ${plan.highlighted ? "text-indigo-200" : "text-slate-400"}`}>
                    {plan.period}
                  </span>
                </div>
                <p className={`text-sm mb-6 ${plan.highlighted ? "text-indigo-200" : "text-slate-400"}`}>
                  {plan.description}
                </p>
                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map((feat) => (
                    <li key={feat} className="flex items-start gap-3 text-sm">
                      <Check size={16} className={`mt-0.5 shrink-0 ${plan.highlighted ? "text-indigo-200" : "text-indigo-400"}`} />
                      <span className={plan.highlighted ? "text-indigo-100" : "text-slate-300"}>{feat}</span>
                    </li>
                  ))}
                </ul>
                <Link
                  href={plan.href}
                  className={`w-full text-center py-3 rounded-xl font-semibold transition-all ${
                    plan.highlighted
                      ? "bg-white text-indigo-600 hover:bg-indigo-50"
                      : "bg-indigo-600 hover:bg-indigo-500 text-white"
                  }`}
                >
                  {plan.cta}
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ───────────────────────────────────────────────────── */}
      <section className="py-24 px-6">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Frequently asked</h2>
          <div className="space-y-4">
            {faqs.map((faq) => (
              <div key={faq.q} className="glass rounded-xl p-6">
                <h3 className="font-semibold text-white mb-2">{faq.q}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────────── */}
      <section className="py-24 px-6 text-center">
        <div className="max-w-xl mx-auto">
          <h2 className="text-4xl font-bold mb-4">Ready to try FRIDAY?</h2>
          <p className="text-slate-400 mb-8">Free forever. No credit card required.</p>
          <Link href="/sign-up" className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-10 py-4 rounded-xl font-semibold text-lg transition-all hover:scale-105 hover:shadow-lg hover:shadow-indigo-500/25">
            <Mic size={20} /> Start for free
          </Link>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-10 px-6 text-center text-slate-500 text-sm">
        <p>© 2026 FRIDAY. Built with ❤️ and Groq.</p>
      </footer>
    </div>
  );
}

function ChatBubble({ side, text }: { side: "user" | "friday"; text: string }) {
  return (
    <div className={`flex gap-3 ${side === "user" ? "flex-row-reverse" : ""}`}>
      <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
        side === "friday" ? "bg-indigo-600 text-white" : "bg-slate-700 text-slate-300"
      }`}>
        {side === "friday" ? "F" : "U"}
      </div>
      <div className={`px-4 py-2.5 rounded-2xl text-sm max-w-xs leading-relaxed ${
        side === "friday"
          ? "bg-white/5 border border-white/8 text-slate-200 rounded-tl-sm"
          : "bg-indigo-600 text-white rounded-tr-sm"
      }`}>
        {text}
      </div>
    </div>
  );
}
