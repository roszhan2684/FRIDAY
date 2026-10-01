import { NextRequest, NextResponse } from "next/server";
import Groq from "groq-sdk";

function getGroq() { return new Groq({ apiKey: process.env.GROQ_API_KEY ?? "placeholder" }); }

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const audio    = formData.get("audio") as File | null;

  if (!audio) return NextResponse.json({ error: "audio required" }, { status: 400 });

  try {
    const transcription = await getGroq().audio.transcriptions.create({
      file:     audio,
      model:    "whisper-large-v3-turbo",
      language: "en",
    });
    return NextResponse.json({ text: transcription.text });
  } catch (err) {
    console.error("Transcription error:", err);
    return NextResponse.json({ error: "transcription failed" }, { status: 500 });
  }
}

// bodyParser disabled by default in Next.js App Router — no config needed
