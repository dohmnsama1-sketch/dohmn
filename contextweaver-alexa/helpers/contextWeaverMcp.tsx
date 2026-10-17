export type ContextFact = {
  fact: string;
  source: string;
  reason: string;
  access: string;
};

export type ContextReceipt = {
  intent: string;
  selectedFacts: ContextFact[];
  withheld: { count: number; reason: string };
  writesRequested: number;
  receiptVersion: string;
  provenanceMode?: string;
};

export type ActionNode = {
  id: string;
  label: string;
  durationMinutes: number;
  permission: string;
  reversible: boolean;
};

export type ActionGraph = {
  intent: string;
  nodes: ActionNode[];
  invariants: string[];
  contextFactCount: number;
  approvalRequired: boolean;
  budgetMinutes: number;
  plannedMinutes: number;
  slackMinutes: number;
  constraintProof: {
    exactBudgetFit: boolean;
    departureBufferProtected: boolean;
    conservation: string;
  };
};

export type ActionExplanation = {
  nodeId: string;
  explanation: {
    why: string;
    dataUsed: string[];
    externalAccess: string;
    approvalRequired: boolean;
  };
};

type JsonRpcResponse<T> = {
  jsonrpc: "2.0";
  id: number;
  result?: {
    structuredContent?: T;
    isError?: boolean;
    content?: Array<{ type: string; text?: string }>;
  };
  error?: { code: number; message: string };
};

let requestId = 100;

export type DemoConstraints = {
  minutesAvailable: number;
  departureTime?: string;
};

function normalizeClock(hourText: string, minuteText: string | undefined, meridiemText: string | undefined) {
  let hour = Number(hourText);
  const minute = minuteText === undefined ? 0 : Number(minuteText);
  if (!Number.isInteger(hour) || !Number.isInteger(minute) || minute < 0 || minute > 59) return null;

  const meridiem = meridiemText?.replace(/\./g, "").toLowerCase();
  if (meridiem) {
    if (hour < 1 || hour > 12) return null;
    if (meridiem === "pm" && hour !== 12) hour += 12;
    if (meridiem === "am" && hour === 12) hour = 0;
  } else if (hour < 0 || hour > 23) {
    return null;
  }

  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/**
 * The web demo has no Alexa+ NLU access, so it extracts only explicit time
 * constraints from the text the judge typed. It deliberately does not infer
 * calendar state, timezone, routine, or hidden memory.
 */
export function parseDemoConstraints(intent: string): DemoConstraints {
  const minuteMatch = intent.match(/\b(\d{1,4})\s*(?:minutes?|mins?|min)\b/i);
  const hourMatch = intent.match(/\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr)\b/i);
  const halfHourMatch = /\bhalf\s+(?:an?\s+)?hour\b/i.test(intent);
  const oneHourMatch = /\b(?:an?|one)\s+hour\b/i.test(intent);

  const explicitHourMinutes = hourMatch
    ? Math.round(Number(hourMatch[1]) * 60)
    : halfHourMatch
      ? 30
      : oneHourMatch
        ? 60
        : 0;
  const explicitMinuteRemainder = minuteMatch ? Number(minuteMatch[1]) : 0;
  const hasExplicitDuration = Boolean(minuteMatch || hourMatch || halfHourMatch || oneHourMatch);
  let minutesAvailable = hasExplicitDuration
    ? explicitHourMinutes + explicitMinuteRemainder
    : 45;
  if (
    !Number.isInteger(minutesAvailable) ||
    minutesAvailable < 0 ||
    minutesAvailable > 1440 ||
    (minutesAvailable > 0 && minutesAvailable < 5)
  ) {
    minutesAvailable = 45;
  }

  const departureMatch = intent.match(
    /\b(?:leave|depart|departure)\b[^0-9]{0,24}(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?/i,
  );
  const departureTime = departureMatch
    ? normalizeClock(departureMatch[1], departureMatch[2], departureMatch[3])
    : null;

  return {
    minutesAvailable,
    ...(departureTime ? { departureTime } : {}),
  };
}

async function callMcpTool<T>(name: string, args: Record<string, unknown>): Promise<T> {
  requestId += 1;
  const response = await fetch("/_api/mcp", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      "MCP-Protocol-Version": "2025-11-25",
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: requestId,
      method: "tools/call",
      params: { name, arguments: args },
    }),
  });

  const payload = (await response.json()) as JsonRpcResponse<T>;
  if (!response.ok || payload.error) {
    throw new Error(payload.error?.message ?? "ContextWeaver MCP request failed");
  }
  if (payload.result?.isError || !payload.result?.structuredContent) {
    const toolMessage = payload.result?.content?.find((item) => item.type === "text")?.text;
    throw new Error(toolMessage ?? "ContextWeaver tool returned no structured result");
  }
  return payload.result.structuredContent;
}

export async function weaveLiveContext(intent: string): Promise<ContextReceipt> {
  const constraints = parseDemoConstraints(intent);
  return callMcpTool<ContextReceipt>("weave_context", {
    intent,
    ...constraints,
  });
}

export async function buildLiveActionGraph(intent: string, receipt: ContextReceipt): Promise<ActionGraph> {
  return callMcpTool<ActionGraph>("build_action_graph", {
    intent,
    contextFacts: receipt.selectedFacts.map((item) => item.fact),
  });
}

export async function explainLiveAction(nodeId: string): Promise<ActionExplanation> {
  return callMcpTool<ActionExplanation>("explain_action", { nodeId });
}