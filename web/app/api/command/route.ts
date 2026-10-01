import { NextRequest, NextResponse } from "next/server";
import { plan } from "@/lib/planner";
import { dispatch } from "@/lib/tools";
import { logInteraction } from "@/lib/db";
import { auth } from "@clerk/nextjs/server";

export async function POST(req: NextRequest) {
  const { text } = await req.json();
  if (!text?.trim()) return NextResponse.json({ error: "text required" }, { status: 400 });

  // Get user — fall back to anonymous session if not signed in
  let userId = "anon";
  try {
    const session = await auth();
    if (session?.userId) userId = session.userId;
  } catch { /* Clerk not configured */ }

  const planResult = await plan(text);
  const toolResult = await dispatch(planResult.tool, planResult.args, userId);

  // Log interaction (best-effort)
  try {
    if (userId !== "anon") {
      await logInteraction(userId, text, planResult.tool, toolResult.output);
    }
  } catch { /* non-blocking */ }

  return NextResponse.json({
    tool:             planResult.tool,
    spoken_response:  toolResult.spoken_response,
    output:           toolResult.output,
    url:              toolResult.url,
  });
}
