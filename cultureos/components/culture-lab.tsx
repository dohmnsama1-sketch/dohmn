"use client";

import { FormEvent, useMemo, useState } from "react";
import type { CultureAnalysis } from "../lib/types";

const starterSeeds = "Nike, Oppenheimer, The Weeknd";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function CultureLab() {
  const [brief, setBrief] = useState(
    "A premium recovery-focused running shoe brand launching with a night-run community experience."
  );
  const [market, setMarket] = useState("Riyadh, Saudi Arabia");
  const [seedText, setSeedText] = useState(starterSeeds);
  const [objective, setObjective] = useState(
    "Find culturally coherent creative anchors, partners, venues, and experience cues."
  );
  const [result, setResult] = useState<CultureAnalysis | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const seeds = useMemo(
    () => seedText.split(",").map((item) => item.trim()).filter(Boolean).slice(0, 6),
    [seedText]
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brief, market, seedTerms: seeds, objective })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Analysis failed.");
      setResult(payload);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="workspace">
      <form className="panel inputPanel" onSubmit={submit}>
        <div className="panelHead">
          <div>
            <span className="kicker">01 / BRIEF</span>
            <h2>Define the launch hypothesis</h2>
          </div>
          <span className="statusDot">LIVE INPUT</span>
        </div>

        <label>
          Product / brand brief
          <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={4} />
        </label>

        <div className="twoCol">
          <label>
            Target market
            <input value={market} onChange={(e) => setMarket(e.target.value)} />
          </label>
          <label>
            Cultural seeds
            <input
              value={seedText}
              onChange={(e) => setSeedText(e.target.value)}
              placeholder="Brand, film, artist, place…"
            />
          </label>
        </div>

        <label>
          Decision objective
          <input value={objective} onChange={(e) => setObjective(e.target.value)} />
        </label>

        <button disabled={loading || seeds.length === 0}>
          {loading ? "Tracing cultural evidence…" : "Run cultural stress test"}
        </button>

        <p className="microcopy">
          Seeds are resolved against Qloo before analysis. No names, emails, device IDs, or other personal data are required.
        </p>
      </form>

      <section className="panel outputPanel" aria-live="polite">
        <div className="panelHead">
          <div>
            <span className="kicker">02 / EVIDENCE</span>
            <h2>Cross-domain cultural map</h2>
          </div>
          {result && <span className="statusDot good">QLOO GROUNDED</span>}
        </div>

        {!result && !error && (
          <div className="emptyState">
            <div className="orb" />
            <h3>Ready for Qloo evidence</h3>
            <p>
              The agent will resolve your seeds, map five cultural domains, and run a counterfactual stability check.
            </p>
          </div>
        )}

        {error && <div className="errorBox">{error}</div>}

        {result && (
          <div className="results">
            <div className="summaryCard">
              <span>Trace summary</span>
              <p>{result.summary}</p>
              <div className="metricRow">
                <strong>{result.provenance.requestCount}</strong>
                <small>Qloo requests</small>
                <strong>{result.resolvedSeeds.length}</strong>
                <small>resolved seeds</small>
                <strong>{result.market.resolvedLocality ? "YES" : "NO"}</strong>
                <small>market resolved</small>
              </div>
            </div>

            <div className="seedRow">
              {result.resolvedSeeds.map((item) => (
                <span key={item.entity.id} title={item.entity.id}>
                  {item.entity.name}
                </span>
              ))}
            </div>

            <div className="lensGrid">
              {result.lenses.map((lens) => (
                <article className="lensCard" key={lens.lens}>
                  <h3>{lens.lens}</h3>
                  <ol>
                    {lens.entities.slice(0, 4).map((entity) => (
                      <li key={entity.id}>
                        <span>{entity.name}</span>
                        {typeof entity.affinity === "number" && (
                          <small>{percent(entity.affinity)}</small>
                        )}
                      </li>
                    ))}
                  </ol>
                </article>
              ))}
            </div>

            {result.stability && (
              <div className="stabilityCard">
                <div>
                  <span className="kicker">COUNTERFACTUAL CHECK</span>
                  <h3>{percent(result.stability.meanOverlap)} mean brand-set retention</h3>
                  <p>
                    Each run removes one seed and checks how much of the Qloo-grounded brand shortlist survives.
                  </p>
                </div>
                <div className="variantList">
                  {result.stability.variants.map((variant) => (
                    <div key={variant.omittedSeed}>
                      <span>without {variant.omittedSeed}</span>
                      <strong>{percent(variant.overlap)}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="bridgeGrid">
              {result.bridges.map((bridge) => (
                <article className="bridgeCard" key={bridge.title}>
                  <span className="kicker">{bridge.title}</span>
                  <p>{bridge.rationale}</p>
                  <div className="evidenceLine">
                    {bridge.evidence.map((item) => (
                      <span key={item.id}>{item.name} · {item.lens}</span>
                    ))}
                  </div>
                </article>
              ))}
            </div>

            <details>
              <summary>Provenance & limitations</summary>
              <ul>
                {result.provenance.limitations.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </details>
          </div>
        )}
      </section>
    </section>
  );
}
