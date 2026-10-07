import type {
  AnalyzeInput,
  CultureAnalysis,
  LensKey,
  LensResult,
  QlooEntity,
  StabilityResult
} from "../types";
import type { TasteGraphClient } from "../qloo/client";

const LENSES: Array<{ lens: LensKey; type: string }> = [
  { lens: "brands", type: "urn:entity:brand" },
  { lens: "places", type: "urn:entity:place" },
  { lens: "artists", type: "urn:entity:artist" },
  { lens: "movies", type: "urn:entity:movie" },
  { lens: "destinations", type: "urn:entity:destination" }
];

function dedupeEntities(items: QlooEntity[]): QlooEntity[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function overlapRatio(a: string[], b: string[]): number {
  if (a.length === 0) return 0;
  const right = new Set(b);
  return a.filter((id) => right.has(id)).length / a.length;
}

function bridgeFromLenses(lenses: LensResult[]) {
  const ranked = lenses
    .flatMap((lens) =>
      lens.entities.slice(0, 2).map((entity, index) => ({
        lens: lens.lens,
        entity,
        rank: index + 1
      }))
    )
    .sort((a, b) => {
      const affinityA = a.entity.affinity ?? 0;
      const affinityB = b.entity.affinity ?? 0;
      if (affinityA !== affinityB) return affinityB - affinityA;
      return a.rank - b.rank;
    });

  const first = ranked[0];
  const firstCross = ranked.find((item) => item.lens !== first?.lens);
  const third = ranked[2];
  const secondCross = ranked.find(
    (item) => item.lens !== third?.lens && item.entity.id !== first?.entity.id
  );

  return [
    first && firstCross ? [first, firstCross] : null,
    third && secondCross ? [third, secondCross] : null
  ]
    .filter(
      (pair): pair is [NonNullable<typeof first>, NonNullable<typeof firstCross>] =>
        Boolean(pair)
    )
    .map(([a, b], index) => ({
      title: index === 0 ? "Primary cultural bridge" : "Alternative cultural bridge",
      rationale:
        `Combine ${a.entity.name} (${a.lens}) with ${b.entity.name} (${b.lens}) as a cross-domain creative anchor. ` +
        "Both are surfaced from the same Qloo-grounded seed set, so the connection is evidence-backed rather than a generic association.",
      evidence: [
        { name: a.entity.name, lens: a.lens, id: a.entity.id },
        { name: b.entity.name, lens: b.lens, id: b.entity.id }
      ]
    }));
}

async function resolveSeeds(client: TasteGraphClient, terms: string[]) {
  const resolved: Array<{ query: string; entity: QlooEntity }> = [];
  for (const term of terms) {
    const matches = await client.searchEntity(term);
    const first = matches[0];
    if (first && !resolved.some((item) => item.entity.id === first.id)) {
      resolved.push({ query: term, entity: first });
    }
  }
  return resolved;
}

async function stabilityCheck(
  client: TasteGraphClient,
  seedEntities: QlooEntity[]
): Promise<StabilityResult | null> {
  if (seedEntities.length < 2) return null;

  const baseline = await client.insights({
    type: "urn:entity:brand",
    seedIds: seedEntities.map((entity) => entity.id),
    take: 5
  });

  const baselineIds = baseline.map((entity) => entity.id);
  const variants = [];

  for (const omitted of seedEntities.slice(0, 3)) {
    const remainingIds = seedEntities
      .filter((entity) => entity.id !== omitted.id)
      .map((entity) => entity.id);

    const variant = await client.insights({
      type: "urn:entity:brand",
      seedIds: remainingIds,
      take: 5
    });

    const variantIds = variant.map((entity) => entity.id);
    variants.push({
      omittedSeed: omitted.name,
      overlap: overlapRatio(baselineIds, variantIds),
      retained: baseline
        .filter((entity) => variantIds.includes(entity.id))
        .map((entity) => entity.name)
    });
  }

  return {
    baselineIds,
    variants,
    meanOverlap:
      variants.reduce((sum, item) => sum + item.overlap, 0) / Math.max(variants.length, 1)
  };
}

export async function analyzeCulture(
  client: TasteGraphClient,
  input: AnalyzeInput
): Promise<CultureAnalysis> {
  const localityMatches = await client.searchEntity(input.market, ["urn:entity:locality"]);
  const resolvedLocality = localityMatches[0] ?? null;

  const resolvedSeeds = await resolveSeeds(client, input.seedTerms);
  if (resolvedSeeds.length === 0) {
    throw new Error(
      "None of the cultural seeds could be resolved in Qloo. Try recognizable brands, artists, films, places, or destinations."
    );
  }

  const seedIds = resolvedSeeds.map((item) => item.entity.id);
  const lenses: LensResult[] = [];

  for (const definition of LENSES) {
    const entities = await client.insights({
      type: definition.type,
      seedIds,
      localityId: resolvedLocality?.id,
      take: 6
    });

    lenses.push({
      lens: definition.lens,
      entityType: definition.type,
      entities: dedupeEntities(entities).slice(0, 6)
    });
  }

  const stability = await stabilityCheck(
    client,
    resolvedSeeds.map((item) => item.entity)
  );

  return {
    summary:
      `CultureOS resolved ${resolvedSeeds.length} cultural seed${resolvedSeeds.length === 1 ? "" : "s"} and tested them across ${lenses.length} Qloo domains` +
      (resolvedLocality ? ` with ${resolvedLocality.name} as the geographic context.` : "."),
    market: {
      query: input.market,
      resolvedLocality
    },
    resolvedSeeds,
    lenses,
    stability,
    bridges: bridgeFromLenses(lenses),
    provenance: {
      source: "Qloo",
      generatedAt: new Date().toISOString(),
      requestCount: client.getRequestCount(),
      limitations: [
        "Qloo outputs represent aggregate affinities, not causal relationships.",
        "No result should be interpreted as a prediction about a specific person.",
        "CultureOS sends cultural seed terms and market context only; it does not require personal identifiers.",
        "Counterfactual stability is an overlap diagnostic, not a statistical confidence interval."
      ]
    }
  };
}
