import { handle } from "../endpoints/mcp_POST";
import { handle as handleGet } from "../endpoints/mcp_GET";

function mcpRequest(method: string, params?: Record<string, unknown>, id: number | undefined = 1) {
  return new Request("https://contextweaver.example/_api/mcp", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      "MCP-Protocol-Version": "2025-11-25",
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      ...(id === undefined ? {} : { id }),
      method,
      ...(params ? { params } : {}),
    }),
  });
}

describe("ContextWeaver MCP 2025-11-25 surface", () => {
  it("negotiates the Alexa+ minimum MCP revision", async () => {
    const response = await handle(
      mcpRequest("initialize", {
        protocolVersion: "2025-11-25",
        capabilities: {},
        clientInfo: { name: "contextweaver-conformance", version: "1.0.0" },
      }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("MCP-Protocol-Version")).toBe("2025-11-25");
    const body = await response.json();
    expect(body.result.protocolVersion).toBe("2025-11-25");
    expect(body.result.capabilities.tools.listChanged).toBe(false);
    expect(body.result.serverInfo.name).toBe("contextweaver-alexa");
  });

  it("acknowledges initialized notifications without a JSON-RPC body", async () => {
    const response = await handle(mcpRequest("notifications/initialized", undefined, undefined));
    expect(response.status).toBe(202);
    expect(await response.text()).toBe("");
  });

  it("rejects an unsupported post-initialization protocol version", async () => {
    const response = await handle(
      new Request("https://contextweaver.example/_api/mcp", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json, text/event-stream",
          "MCP-Protocol-Version": "2025-06-18",
        },
        body: JSON.stringify({ jsonrpc: "2.0", id: 9, method: "tools/list" }),
      }),
    );
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.error.code).toBe(-32602);
    expect(body.error.data.requested).toBe("2025-06-18");
    expect(body.error.data.supported).toEqual(["2025-11-25"]);
  });

  it("rejects cross-origin Streamable HTTP requests", async () => {
    const response = await handle(
      new Request("https://contextweaver.example/_api/mcp", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json, text/event-stream",
          Origin: "https://untrusted.example",
          "MCP-Protocol-Version": "2025-11-25",
        },
        body: JSON.stringify({ jsonrpc: "2.0", id: 10, method: "tools/list" }),
      }),
    );
    expect(response.status).toBe(403);
    const body = await response.json();
    expect(body.error.message).toBe("Forbidden origin");
    expect(response.headers.get("Access-Control-Allow-Origin")).toBeNull();
  });

  it("exposes the same MCP path over GET and explicitly declines SSE with 405", async () => {
    const response = await handleGet(
      new Request("https://contextweaver.example/_api/mcp", {
        method: "GET",
        headers: { Accept: "text/event-stream" },
      }),
    );
    expect(response.status).toBe(405);
    expect(response.headers.get("Allow")).toBe("POST");
    expect(response.headers.get("MCP-Protocol-Version")).toBe("2025-11-25");
    expect(await response.text()).toBe("");
  });

  it("lists tools in a deterministic order", async () => {
    const response = await handle(mcpRequest("tools/list"));
    const body = await response.json();
    expect(body.result.tools.map((tool: { name: string }) => tool.name)).toEqual([
      "weave_context",
      "build_action_graph",
      "explain_action",
    ]);
  });

  it("returns an internally consistent privacy receipt", async () => {
    const response = await handle(
      mcpRequest("tools/call", {
        name: "weave_context",
        arguments: {
          intent: "Help me make the next 45 minutes calm and productive.",
          minutesAvailable: 45,
          departureTime: "07:42",
        },
      }),
    );
    const body = await response.json();
    const receipt = body.result.structuredContent;
    expect(body.result.isError).toBe(false);
    expect(receipt.selectedFacts.length).toBe(3);
    expect(receipt.withheld.count).toBe(15);
    expect(receipt.selectedFacts.length + receipt.withheld.count).toBe(18);
    expect(receipt.writesRequested).toBe(0);
    expect(receipt.provenanceMode).toBe("explicit-demo-input");
    expect(receipt.demoData).toBe(true);
    expect(receipt.dataAccessMode).toBe("explicit-demo-input-only");
    expect(receipt.selectedFacts.every((fact: { access: string }) => fact.access === "local")).toBe(true);
    expect(receipt.selectedFacts.some((fact: { source: string }) => /calendar|memory/i.test(fact.source))).toBe(false);
  });

  it("rejects malformed explicit departure times at the server boundary", async () => {
    const response = await handle(
      mcpRequest("tools/call", {
        name: "weave_context",
        arguments: {
          intent: "Help me plan the next hour.",
          minutesAvailable: 60,
          departureTime: "25:91",
        },
      }),
    );
    const body = await response.json();
    expect(body.result.isError).toBe(true);
    expect(body.result.content[0].text).toContain("24-hour HH:MM");
  });

  it("builds an exactly budgeted reversible graph and rejects blank context facts", async () => {
    const validResponse = await handle(
      mcpRequest("tools/call", {
        name: "build_action_graph",
        arguments: {
          intent: "Protect a calm departure.",
          contextFacts: ["45 minutes available", "quiet starts work better", "departure at 07:42"],
        },
      }),
    );
    const validBody = await validResponse.json();
    const graph = validBody.result.structuredContent;
    expect(graph.nodes.length).toBe(4);
    expect(graph.nodes.every((node: { reversible: boolean }) => node.reversible)).toBe(true);
    expect(graph.approvalRequired).toBe(false);
    expect(graph.invariants).toContain("no external writes");
    expect(graph.invariants).toContain("planned minutes never exceed the available budget");
    expect(graph.budgetMinutes).toBe(45);
    expect(graph.plannedMinutes).toBe(45);
    expect(graph.slackMinutes).toBe(0);
    expect(graph.constraintProof.exactBudgetFit).toBe(true);
    expect(graph.constraintProof.departureBufferProtected).toBe(true);
    expect(graph.nodes.reduce((sum: number, node: { durationMinutes: number }) => sum + node.durationMinutes, 0)).toBe(45);

    const invalidResponse = await handle(
      mcpRequest("tools/call", {
        name: "build_action_graph",
        arguments: { intent: "Test", contextFacts: ["   "] },
      }),
    );
    const invalidBody = await invalidResponse.json();
    expect(invalidBody.result.isError).toBe(true);
  });

  it("fails closed when an action graph has no trustworthy availability budget", async () => {
    const missingBudget = await handle(
      mcpRequest("tools/call", {
        name: "build_action_graph",
        arguments: {
          intent: "Protect a calm departure.",
          contextFacts: ["quiet starts work better", "departure at 08:05"],
        },
      }),
    );
    const missingBody = await missingBudget.json();
    expect(missingBody.result.isError).toBe(true);
    expect(missingBody.result.content[0].text).toContain("5-1440 minute");

    const outOfRange = await handle(
      mcpRequest("tools/call", {
        name: "build_action_graph",
        arguments: {
          intent: "Protect a calm departure.",
          contextFacts: ["2 minutes available", "departure at 08:05"],
        },
      }),
    );
    const outOfRangeBody = await outOfRange.json();
    expect(outOfRangeBody.result.isError).toBe(true);
  });

  it("rejects malformed departure facts instead of claiming a protected buffer", async () => {
    const response = await handle(
      mcpRequest("tools/call", {
        name: "build_action_graph",
        arguments: {
          intent: "Protect a calm departure.",
          contextFacts: ["45 minutes available", "departure at tomorrow-ish"],
        },
      }),
    );
    const body = await response.json();
    expect(body.result.isError).toBe(true);
    expect(body.result.content[0].text).toContain("departure at HH:MM");
  });

  it("rebalances the action graph deterministically for a shorter window", async () => {
    const response = await handle(
      mcpRequest("tools/call", {
        name: "build_action_graph",
        arguments: {
          intent: "Give me a compact plan before I leave.",
          contextFacts: ["17 minutes available", "departure at 08:05"],
        },
      }),
    );
    const body = await response.json();
    const graph = body.result.structuredContent;
    expect(graph.budgetMinutes).toBe(17);
    expect(graph.plannedMinutes).toBe(17);
    expect(graph.nodes.map((node: { id: string }) => node.id)).toEqual(["hydrate", "focus", "breakfast", "buffer"]);
    expect(graph.nodes.reduce((sum: number, node: { durationMinutes: number }) => sum + node.durationMinutes, 0)).toBe(17);
    expect(graph.constraintProof.conservation).toBe("17 = 2 + 8 + 3 + 4");
  });

  it("provides an explanation receipt for every action node", async () => {
    const graphResponse = await handle(
      mcpRequest("tools/call", {
        name: "build_action_graph",
        arguments: {
          intent: "Protect a calm departure.",
          contextFacts: ["45 minutes available", "quiet starts work better", "departure at 07:42"],
        },
      }),
    );
    const graphBody = await graphResponse.json();
    const nodes = graphBody.result.structuredContent.nodes as Array<{ id: string }>;

    for (const node of nodes) {
      const response = await handle(
        mcpRequest("tools/call", {
          name: "explain_action",
          arguments: { nodeId: node.id },
        }),
      );
      const body = await response.json();
      expect(body.result.isError).toBe(false);
      expect(body.result.structuredContent.nodeId).toBe(node.id);
      expect(body.result.structuredContent.explanation.why.length).toBeGreaterThan(20);
      expect(body.result.structuredContent.explanation.externalAccess).toBe("none");
      expect(body.result.structuredContent.explanation.approvalRequired).toBe(false);
    }
  });
});