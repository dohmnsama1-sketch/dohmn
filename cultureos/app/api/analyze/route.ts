import { NextResponse } from "next/server";
import { analyzeCulture } from "../../../lib/agent/orchestrator";
import { QlooClient } from "../../../lib/qloo/client";
import type { AnalyzeInput } from "../../../lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function cleanText(value: unknown, max: number): string {
  if (typeof value !== "string") return "";
  return value.replace(/[<>]/g, "").trim().slice(0, max);
}

export async function POST(request: Request) {
  try {
    const raw = await request.json();
    const input: AnalyzeInput = {
      brief: cleanText(raw.brief, 1200),
      market: cleanText(raw.market, 120),
      seedTerms: Array.isArray(raw.seedTerms)
        ? raw.seedTerms.map((v: unknown) => cleanText(v, 120)).filter(Boolean).slice(0, 6)
        : [],
      objective: cleanText(raw.objective, 300)
    };

    if (input.brief.length < 12 || input.market.length < 2 || input.seedTerms.length === 0) {
      return NextResponse.json(
        { error: "Provide a clear brief, target market, and at least one cultural seed." },
        { status: 400 }
      );
    }

    const apiKey = process.env.QLOO_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "Qloo access is not configured yet. The project is waiting for its event API key." },
        { status: 503 }
      );
    }

    const client = new QlooClient({
      apiKey,
      baseUrl: process.env.QLOO_BASE_URL || "https://hackathon.api.qloo.com"
    });

    const result = await analyzeCulture(client, input);
    return NextResponse.json(result, {
      headers: { "Cache-Control": "no-store" }
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unexpected analysis failure.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
