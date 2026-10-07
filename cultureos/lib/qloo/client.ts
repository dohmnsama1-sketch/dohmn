import type { QlooEntity } from "../types";

type ClientConfig = {
  apiKey: string;
  baseUrl: string;
};

export interface TasteGraphClient {
  searchEntity(query: string, types?: string[]): Promise<QlooEntity[]>;
  insights(input: {
    type: string;
    seedIds: string[];
    localityId?: string;
    take?: number;
  }): Promise<QlooEntity[]>;
  getRequestCount(): number;
}

function toEntity(value: unknown): QlooEntity | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const id = String(item.id ?? item.entity_id ?? item.qloo_id ?? "");
  const name = String(item.name ?? item.title ?? item.label ?? "");
  if (!id || !name) return null;

  const affinityRaw = item.affinity ?? item.score ?? item.query_affinity;
  const popularityRaw = item.popularity ?? item.popularity_score;

  return {
    id,
    name,
    type: typeof item.type === "string" ? item.type : undefined,
    affinity: typeof affinityRaw === "number" ? affinityRaw : undefined,
    popularity: typeof popularityRaw === "number" ? popularityRaw : undefined,
    properties:
      item.properties && typeof item.properties === "object"
        ? (item.properties as Record<string, unknown>)
        : undefined
  };
}

function findEntityArray(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== "object") return [];
  const root = payload as Record<string, unknown>;

  for (const candidate of [root.entities, root.results, root.data, root.items]) {
    if (Array.isArray(candidate)) return candidate;
    if (candidate && typeof candidate === "object") {
      const nested = candidate as Record<string, unknown>;
      for (const key of ["entities", "results", "items"]) {
        if (Array.isArray(nested[key])) return nested[key] as unknown[];
      }
    }
  }
  return [];
}

export class QlooClient implements TasteGraphClient {
  private requestCount = 0;

  constructor(private readonly config: ClientConfig) {}

  getRequestCount(): number {
    return this.requestCount;
  }

  private async get(path: string, params: URLSearchParams): Promise<unknown> {
    const url = new URL(path, this.config.baseUrl);
    url.search = params.toString();

    let lastError: Error | null = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      this.requestCount += 1;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 9000);

      try {
        const response = await fetch(url, {
          method: "GET",
          headers: {
            "X-Api-Key": this.config.apiKey,
            Accept: "application/json"
          },
          signal: controller.signal,
          cache: "no-store"
        });

        const text = await response.text();
        const payload = text ? JSON.parse(text) : {};

        if (response.ok) return payload;

        if ((response.status === 429 || response.status >= 500) && attempt === 0) {
          await new Promise((resolve) => setTimeout(resolve, 300));
          continue;
        }

        const providerMessage =
          payload && typeof payload === "object" && typeof (payload as Record<string, unknown>).message === "string"
            ? String((payload as Record<string, unknown>).message)
            : "Check the request parameters.";
        throw new Error(`Qloo request failed (${response.status}). ${providerMessage}`);
      } catch (error) {
        lastError =
          error instanceof Error ? error : new Error("Qloo request failed for an unknown reason.");
        if (attempt === 0 && lastError.name === "AbortError") continue;
        throw lastError;
      } finally {
        clearTimeout(timer);
      }
    }

    throw lastError ?? new Error("Qloo request failed.");
  }

  async searchEntity(query: string, types: string[] = []): Promise<QlooEntity[]> {
    const params = new URLSearchParams();
    params.set("query", query);
    params.set("take", "5");
    for (const type of types) params.append("types", type);

    const payload = await this.get("/search", params);
    return findEntityArray(payload).map(toEntity).filter((v): v is QlooEntity => Boolean(v));
  }

  async insights(input: {
    type: string;
    seedIds: string[];
    localityId?: string;
    take?: number;
  }): Promise<QlooEntity[]> {
    const params = new URLSearchParams();
    params.set("filter.type", input.type);
    params.set("take", String(Math.min(Math.max(input.take ?? 5, 1), 10)));

    for (const id of input.seedIds) params.append("signal.interests.entities", id);
    if (input.localityId && ["urn:entity:place", "urn:entity:destination"].includes(input.type)) {
      params.set("filter.location", input.localityId);
    }

    const payload = await this.get("/v2/insights", params);
    return findEntityArray(payload).map(toEntity).filter((v): v is QlooEntity => Boolean(v));
  }
}
