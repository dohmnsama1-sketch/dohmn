import { handle } from "../endpoints/mcp_POST";

function callGraph(minutes: number, includeDeparture = true) {
  return handle(
    new Request("https://contextweaver.example/_api/mcp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-11-25",
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: minutes,
        method: "tools/call",
        params: {
          name: "build_action_graph",
          arguments: {
            intent: "Build a constraint-safe plan.",
            contextFacts: [
              `${minutes} minutes available`,
              "quiet starts work better",
              ...(includeDeparture ? ["departure at 08:05"] : []),
            ],
          },
        },
      }),
    }),
  );
}

describe("ContextWeaver constraint-budget benchmark", () => {
  const windows = [5, 17, 30, 45, 60, 90, 180];

  for (const minutes of windows) {
    it(`fits a departure-aware graph exactly inside ${minutes} minutes`, async () => {
      const response = await callGraph(minutes, true);
      const body = await response.json();
      const graph = body.result.structuredContent;

      expect(body.result.isError).toBe(false);
      expect(graph.budgetMinutes).toBe(minutes);
      expect(graph.plannedMinutes).toBe(minutes);
      expect(graph.slackMinutes).toBe(0);
      expect(graph.constraintProof.exactBudgetFit).toBe(true);
      expect(graph.constraintProof.departureBufferProtected).toBe(true);
      expect(graph.nodes.map((node: { id: string }) => node.id)).toEqual([
        "hydrate",
        "focus",
        "breakfast",
        "buffer",
      ]);
      expect(
        graph.nodes.reduce(
          (sum: number, node: { durationMinutes: number }) => sum + node.durationMinutes,
          0,
        ),
      ).toBe(minutes);
      expect(graph.nodes.every((node: { durationMinutes: number }) => node.durationMinutes >= 1)).toBe(true);
    });
  }

  it("returns an empty graph for an explicit zero-minute budget", async () => {
    const response = await callGraph(0, false);
    const body = await response.json();
    const graph = body.result.structuredContent;

    expect(body.result.isError).toBe(false);
    expect(graph.budgetMinutes).toBe(0);
    expect(graph.plannedMinutes).toBe(0);
    expect(graph.slackMinutes).toBe(0);
    expect(graph.nodes).toEqual([]);
    expect(graph.constraintProof.exactBudgetFit).toBe(true);
    expect(graph.constraintProof.conservation).toBe("0 = 0");
  });

  it("removes the departure-only node when no departure fact is approved", async () => {
    const response = await callGraph(45, false);
    const body = await response.json();
    const graph = body.result.structuredContent;

    expect(graph.plannedMinutes).toBe(45);
    expect(graph.nodes.map((node: { id: string }) => node.id)).toEqual([
      "hydrate",
      "focus",
      "breakfast",
    ]);
    expect(graph.constraintProof.departureBufferProtected).toBe(false);
    expect(graph.invariants).not.toContain("departure buffer cannot be consumed");
  });

  it("is deterministic for identical approved context", async () => {
    const first = await (await callGraph(45, true)).json();
    const second = await (await callGraph(45, true)).json();
    expect(second.result.structuredContent).toEqual(first.result.structuredContent);
  });
});
