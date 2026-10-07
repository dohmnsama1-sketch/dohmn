import { describe, expect, it } from "vitest";
import { analyzeCulture } from "../lib/agent/orchestrator";
import type { QlooEntity } from "../lib/types";
import type { TasteGraphClient } from "../lib/qloo/client";

class FakeClient implements TasteGraphClient {
  count = 0;

  getRequestCount() {
    return this.count;
  }

  async searchEntity(query: string, types: string[] = []) {
    this.count += 1;
    if (types.includes("urn:entity:locality")) {
      return [{ id: "loc-riyadh", name: "Riyadh", type: "urn:entity:locality" }];
    }
    return [{ id: `seed-${query.toLowerCase().replace(/\s+/g, "-")}`, name: query }];
  }

  async insights(input: { type: string; seedIds: string[]; localityId?: string; take?: number }) {
    this.count += 1;
    const label = input.type.split(":").pop() || "entity";
    const entities: QlooEntity[] = Array.from({ length: input.take ?? 5 }, (_, i) => ({
      id: `${label}-${i}`,
      name: `${label} ${i + 1}`,
      type: input.type,
      affinity: 0.9 - i * 0.08
    }));
    return entities;
  }
}

describe("CultureOS orchestration", () => {
  it("resolves market and seeds, maps five lenses, and produces bridges", async () => {
    const client = new FakeClient();
    const result = await analyzeCulture(client, {
      brief: "A premium recovery running shoe launch.",
      market: "Riyadh, Saudi Arabia",
      seedTerms: ["Nike", "The Weeknd"],
      objective: "Find cultural anchors"
    });

    expect(result.market.resolvedLocality?.name).toBe("Riyadh");
    expect(result.resolvedSeeds).toHaveLength(2);
    expect(result.lenses).toHaveLength(5);
    expect(result.bridges.length).toBeGreaterThan(0);
    expect(result.stability).not.toBeNull();
    expect(result.provenance.source).toBe("Qloo");
    expect(result.provenance.requestCount).toBe(client.getRequestCount());
  });

  it("refuses to fabricate analysis when Qloo resolves no seeds", async () => {
    const client = new FakeClient();
    client.searchEntity = async (_query: string, types: string[] = []) => {
      client.count += 1;
      if (types.includes("urn:entity:locality")) return [];
      return [];
    };

    await expect(
      analyzeCulture(client, {
        brief: "A valid product brief long enough.",
        market: "Riyadh",
        seedTerms: ["Unknown seed"]
      })
    ).rejects.toThrow(/could be resolved in Qloo/);
  });
});
