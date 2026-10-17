type JsonRpcId = string | number | null;

type JsonRpcRequest = {
  jsonrpc?: string;
  id?: JsonRpcId;
  method?: string;
  params?: Record<string, unknown>;
};

const PROTOCOL_VERSION = "2025-11-25";
const SERVER_INFO = { name: "contextweaver-alexa", version: "0.1.0" };
const MIN_BUDGET_MINUTES = 5;
const MAX_BUDGET_MINUTES = 1440;

function isValidLocalClock(value: string) {
  return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
}

function responseHeaders(request: Request) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Access-Control-Allow-Headers": "content-type, accept, mcp-protocol-version, mcp-session-id",
    "Access-Control-Expose-Headers": "MCP-Protocol-Version",
    "MCP-Protocol-Version": PROTOCOL_VERSION
  };
  const origin = request.headers.get("origin");
  if (origin && origin === new URL(request.url).origin) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Vary"] = "Origin";
  }
  return headers;
}

function hasValidOrigin(request: Request) {
  const origin = request.headers.get("origin");
  return !origin || origin === new URL(request.url).origin;
}

const tools = [
  {
    name: "weave_context",
    title: "Weave relevant context",
    description: "Select only context facts that materially change the answer and return a privacy receipt explaining why each fact was used.",
    inputSchema: {
      type: "object",
      properties: {
        intent: { type: "string", minLength: 1, description: "The user's natural-language intent." },
        minutesAvailable: { type: "integer", minimum: 0, maximum: 1440 },
        departureTime: { type: "string", description: "Optional local departure time such as 07:42." }
      },
      required: ["intent", "minutesAvailable"],
      additionalProperties: false
    }
  },
  {
    name: "build_action_graph",
    title: "Build an inspectable action graph",
    description: "Turn an intent and approved context facts into a compact, reversible sequence of actions with permission labels.",
    inputSchema: {
      type: "object",
      properties: {
        intent: { type: "string", minLength: 1 },
        contextFacts: { type: "array", items: { type: "string", minLength: 1 }, minItems: 1, maxItems: 12 }
      },
      required: ["intent", "contextFacts"],
      additionalProperties: false
    }
  },
  {
    name: "explain_action",
    title: "Explain an action before execution",
    description: "Explain why a proposed action exists, what data it uses, whether it reads or writes externally, and whether approval is required.",
    inputSchema: {
      type: "object",
      properties: {
        nodeId: { type: "string", enum: ["hydrate", "focus", "breakfast", "buffer"] }
      },
      required: ["nodeId"],
      additionalProperties: false
    }
  }
] as const;

function jsonRpcResult(id: JsonRpcId | undefined, result: unknown) {
  return { jsonrpc: "2.0", id: id ?? null, result };
}

function jsonRpcError(id: JsonRpcId | undefined, code: number, message: string, data?: unknown) {
  return { jsonrpc: "2.0", id: id ?? null, error: { code, message, ...(data === undefined ? {} : { data }) } };
}

function toolText(payload: unknown) {
  return {
    content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
    structuredContent: payload,
    isError: false
  };
}

function callTool(name: unknown, args: unknown) {
  const input = (args && typeof args === "object" ? args : {}) as Record<string, unknown>;

  if (name === "weave_context") {
    const intent = typeof input.intent === "string" ? input.intent.trim() : "";
    const minutes = Number(input.minutesAvailable);
    if (
      !intent ||
      !Number.isInteger(minutes) ||
      minutes < 0 ||
      minutes > MAX_BUDGET_MINUTES ||
      (minutes > 0 && minutes < MIN_BUDGET_MINUTES)
    ) {
      return { error: "intent and a valid minutesAvailable value are required" };
    }
    const departure = typeof input.departureTime === "string" && input.departureTime.trim() ? input.departureTime.trim() : null;
    if (departure && !isValidLocalClock(departure)) {
      return { error: "departureTime must use 24-hour HH:MM format" };
    }
    return toolText({
      intent,
      selectedFacts: [
        { fact: minutes + " minutes available", source: "explicit demo input", reason: "hard scheduling constraint", access: "local" },
        { fact: "quiet starts work better", source: "explicit demo fixture", reason: "reduces unnecessary task switching", access: "local" },
        ...(departure ? [{ fact: "departure at " + departure, source: "explicit demo input", reason: "protects a departure buffer", access: "local" }] : [])
      ],
      withheld: { count: departure ? 15 : 16, reason: "not relevant enough to change this answer" },
      writesRequested: 0,
      receiptVersion: "cw-context-v1",
      provenanceMode: "explicit-demo-input",
      demoData: true,
      dataAccessMode: "explicit-demo-input-only"
    });
  }

  if (name === "build_action_graph") {
    const intent = typeof input.intent === "string" ? input.intent.trim() : "";
    const facts = Array.isArray(input.contextFacts)
      ? input.contextFacts
          .filter((item): item is string => typeof item === "string")
          .map((item) => item.trim())
          .filter(Boolean)
          .slice(0, 12)
      : [];
    if (!intent || facts.length === 0) return { error: "intent and at least one contextFact are required" };

    const budgetFact = facts.find((fact) => /\b\d+\s+minutes?\s+available\b/i.test(fact));
    const parsedBudget = budgetFact?.match(/\b(\d+)\s+minutes?\s+available\b/i);
    const budgetMinutes = parsedBudget ? Number(parsedBudget[1]) : null;
    if (
      budgetMinutes === null ||
      !Number.isInteger(budgetMinutes) ||
      budgetMinutes < 0 ||
      budgetMinutes > MAX_BUDGET_MINUTES ||
      (budgetMinutes > 0 && budgetMinutes < MIN_BUDGET_MINUTES)
    ) {
      return { error: "contextFacts must include a valid 5-1440 minute availability budget" };
    }

    const departureFacts = facts.filter((fact) => /^departure\s+at\s+/i.test(fact));
    const invalidDepartureFact = departureFacts.find((fact) => {
      const match = fact.match(/^departure\s+at\s+(.+)$/i);
      return !match || !isValidLocalClock(match[1].trim());
    });
    if (invalidDepartureFact) {
      return { error: "departure context must use 'departure at HH:MM' with a valid 24-hour clock" };
    }
    const hasDeparture = departureFacts.length > 0;

    const weightedPlan = budgetMinutes === 0
      ? []
      : hasDeparture
      ? [
          { id: "hydrate", label: "Water + reset", weight: 0.10, permission: "none" },
          { id: "focus", label: "Single focused review block", weight: 0.50, permission: "none" },
          { id: "breakfast", label: "Breakfast + coffee", weight: 0.18, permission: "none" },
          { id: "buffer", label: "Protected departure buffer", weight: 0.22, permission: "local-context" }
        ]
      : [
          { id: "hydrate", label: "Water + reset", weight: 0.12, permission: "none" },
          { id: "focus", label: "Single focused review block", weight: 0.65, permission: "none" },
          { id: "breakfast", label: "Breakfast + coffee", weight: 0.23, permission: "none" }
        ];

    const rawDurations = weightedPlan.map((node) => budgetMinutes * node.weight);
    const durations = rawDurations.map((value) => Math.floor(value));
    let remainder = budgetMinutes - durations.reduce((sum, value) => sum + value, 0);
    const remainderOrder = rawDurations
      .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
      .sort((a, b) => b.fraction - a.fraction || a.index - b.index);
    for (let i = 0; i < remainder; i += 1) {
      durations[remainderOrder[i % remainderOrder.length].index] += 1;
    }

    const nodes = weightedPlan.map((node, index) => ({
      id: node.id,
      label: node.label,
      durationMinutes: durations[index],
      permission: node.permission,
      reversible: true
    }));
    const plannedMinutes = nodes.reduce((sum, node) => sum + node.durationMinutes, 0);

    return toolText({
      intent,
      nodes,
      invariants: [
        "planned minutes never exceed the available budget",
        "no external writes",
        "one active priority",
        ...(hasDeparture ? ["departure buffer cannot be consumed"] : [])
      ],
      contextFactCount: facts.length,
      approvalRequired: false,
      budgetMinutes,
      plannedMinutes,
      slackMinutes: budgetMinutes - plannedMinutes,
      constraintProof: {
        exactBudgetFit: plannedMinutes === budgetMinutes,
        departureBufferProtected: hasDeparture,
        conservation: nodes.length
          ? budgetMinutes + " = " + nodes.map((node) => node.durationMinutes).join(" + ")
          : "0 = 0"
      }
    });
  }

  if (name === "explain_action") {
    const nodeId = typeof input.nodeId === "string" ? input.nodeId : "";
    const explanations: Record<string, unknown> = {
      hydrate: { why: "A short physical reset lowers transition friction before the focus block.", dataUsed: ["explicit time budget"], externalAccess: "none", approvalRequired: false },
      focus: { why: "One bounded focus block fits the available window without creating a second unfinished task.", dataUsed: ["minutes available", "demo quiet-start fixture"], externalAccess: "none", approvalRequired: false },
      breakfast: { why: "Breakfast is placed after focus so the plan stays simple while preserving the stated routine.", dataUsed: ["demo quiet-start fixture"], externalAccess: "none", approvalRequired: false },
      buffer: { why: "The buffer is reserved so the assistant cannot optimize the plan at the expense of leaving on time.", dataUsed: ["explicit departure constraint"], externalAccess: "none", approvalRequired: false }
    };
    if (!(nodeId in explanations)) return { error: "unknown nodeId" };
    return toolText({ nodeId, explanation: explanations[nodeId] });
  }

  return { error: "unknown tool" };
}

export async function handle(request: Request) {
  const headers = responseHeaders(request);

  if (!hasValidOrigin(request)) {
    return new Response(
      JSON.stringify(jsonRpcError(null, -32000, "Forbidden origin")),
      { status: 403, headers },
    );
  }

  try {
    const body = JSON.parse(await request.text()) as JsonRpcRequest;
    if (!body || body.jsonrpc !== "2.0" || typeof body.method !== "string") {
      return new Response(JSON.stringify(jsonRpcError(body?.id, -32600, "Invalid Request")), { status: 400, headers });
    }

    if (body.method !== "initialize") {
      const requestedVersion = request.headers.get("mcp-protocol-version") ?? "2025-03-26";
      if (requestedVersion !== PROTOCOL_VERSION) {
        return new Response(
          JSON.stringify(
            jsonRpcError(body.id, -32602, "Unsupported protocol version", {
              supported: [PROTOCOL_VERSION],
              requested: requestedVersion,
            }),
          ),
          { status: 400, headers },
        );
      }
    }

    if (body.method === "notifications/initialized") {
      return new Response(null, { status: 202, headers });
    }

    if (body.method === "initialize") {
      return new Response(JSON.stringify(jsonRpcResult(body.id, {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: { tools: { listChanged: false } },
        serverInfo: SERVER_INFO,
        instructions: "ContextWeaver is a privacy-first Alexa+ orchestration demo. It reads only explicit demo input, not external memory or calendar data. Use weave_context before build_action_graph; use explain_action when the user asks why."
      })), { status: 200, headers });
    }

    if (body.method === "ping") {
      return new Response(JSON.stringify(jsonRpcResult(body.id, {})), { status: 200, headers });
    }

    if (body.method === "tools/list") {
      return new Response(JSON.stringify(jsonRpcResult(body.id, { tools })), { status: 200, headers });
    }

    if (body.method === "tools/call") {
      const params = body.params ?? {};
      const name = params.name;
      const outcome = callTool(name, params.arguments);
      if (outcome && typeof outcome === "object" && "error" in outcome) {
        return new Response(JSON.stringify(jsonRpcResult(body.id, {
          content: [{ type: "text", text: String((outcome as { error: unknown }).error) }],
          isError: true
        })), { status: 200, headers });
      }
      return new Response(JSON.stringify(jsonRpcResult(body.id, outcome)), { status: 200, headers });
    }

    return new Response(JSON.stringify(jsonRpcError(body.id, -32601, "Method not found")), { status: 404, headers });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return new Response(JSON.stringify(jsonRpcError(null, -32700, "Parse error", { message })), { status: 400, headers });
  }
}