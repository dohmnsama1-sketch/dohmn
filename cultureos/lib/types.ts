export type QlooEntity = {
  id: string;
  name: string;
  type?: string;
  affinity?: number;
  popularity?: number;
  properties?: Record<string, unknown>;
};

export type AnalyzeInput = {
  brief: string;
  market: string;
  seedTerms: string[];
  objective?: string;
};

export type LensKey = "brands" | "places" | "artists" | "movies" | "destinations";

export type LensResult = {
  lens: LensKey;
  entityType: string;
  entities: QlooEntity[];
};

export type StabilityResult = {
  baselineIds: string[];
  variants: Array<{
    omittedSeed: string;
    overlap: number;
    retained: string[];
  }>;
  meanOverlap: number;
};

export type CultureAnalysis = {
  summary: string;
  market: {
    query: string;
    resolvedLocality: QlooEntity | null;
  };
  resolvedSeeds: Array<{ query: string; entity: QlooEntity }>;
  lenses: LensResult[];
  stability: StabilityResult | null;
  bridges: Array<{
    title: string;
    rationale: string;
    evidence: Array<{ name: string; lens: LensKey; id: string }>;
  }>;
  provenance: {
    source: "Qloo";
    generatedAt: string;
    requestCount: number;
    limitations: string[];
  };
};
