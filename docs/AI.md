# AI implementation and evidence

MendCart's default AI is a genuine supervised **TF-IDF nearest-neighbor intent classifier**, implemented in Python's standard library. It learns from the committed original synthetic corpus in [`data/intent_corpus.json`](../data/intent_corpus.json). It works without an API key, internet access, downloads, or a paid model service. The default is a small domain model; it is not a pretrained LLM.

## What is learned

At first use, the model reads 72 labeled training phrases across four classes: `pump`, `battery`, `tools`, and `unsupported`. It extracts unigram and adjacent-bigram features, learns inverse-document-frequency weights across the corpus, and builds unit-length TF-IDF training vectors. Each input clause is classified using the average cosine similarity of its three nearest examples in each class. Acceptance requires a winning similarity of at least `0.12`, a margin over the next class of at least `0.035`, and a supported winning class. Scores are retrieval evidence; they are not calibrated probabilities.

This learned classification identifies which catalog family is relevant. Replacing the training corpus changes learned vocabulary, weights, and example neighborhoods. The class decision is not a keyword routing table. The returned decision trace includes the input clause, model decision, score, margin, and nearest labeled examples so judges can inspect the inference.

## Where determinism protects the purchase

After intent inference, bounded parsing extracts counts, four-cell packs, explicit exclusions, simple budget phrases, and named synthetic supplier restrictions. A constraint solver compares repair versus replacement and reclaimed versus new candidate carts. It chooses exactly one alternative per requested category, minimizing repair/reuse priority and then price among carts that meet the request, supplier allowlist, simulated stock, exclusions, and budget. Fallbacks appear as alternatives; they are not purchased alongside the preferred solution.

The structured budget and any recognized budget in the sentence are both enforced, using the lower cap. For example, `Repair two leaking water pumps and buy eight cells, no tools` results in two seal kits and two reclaimed four-cell packs totaling a **synthetic $70**. `Eight protected 18650 cells, only new please` selects two new four-cell packs at a **synthetic $37**. These are calculated demo amounts, not market savings or real quotes.

Unsupported requested goals require clarification rather than silently disappearing. Unknown SKUs, invalid quantities, duplicate alternatives, excluded conditions, unavailable requested categories, unapproved suppliers, and over-budget totals block checkout. An unsatisfied multi-category request cannot pass with a partial cart. The checkout layer separately binds the verified plan to the user's browser session and checks the stored cart again before a PayPal sandbox order.

## Catalog grounding and limits

Every price, supplier, inventory record, condition, compatibility statement, and evidence identifier is a synthetic fixture. Catalog records explicitly carry `synthetic: true` and `SYN-...` evidence IDs. The seal kit's compatibility is limited to the fictional **Demo P100** appliance; MendCart makes no claim that a real pump has been identified or tested. Similarity cannot establish mechanical compatibility, battery safety, a safety certification, or merchant availability.

The local model is intentionally narrow and uses English demo requests. It does not provide diagnosis, general shopping knowledge, live vendor negotiation, arbitrary multilingual language understanding, or autonomous approval of payments. Negation and numeric parsing cover documented English forms and are not a complete natural-language parser. Ambiguous inputs may need rephrasing. Human inspection is still required before any real purchase; this application uses PayPal sandbox only.

## Optional external structured model

Setting all three variables enables the existing OpenAI-compatible adapter:

```text
OPENAI_BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=<stored locally; never commit>
OPENAI_MODEL=<provider model identifier>
```

The adapter sends the request, bounded requirements, exclusions, allowed supplier IDs, budget, and synthetic catalog to `/chat/completions`, requesting JSON with `summary`, `items[{sku,quantity}]`, and `reasoning`. This uses the configured provider and may incur its charges. No external provider is configured or claimed by default. External explanations are model output; the same deterministic SKU, category, quantity, supplier, stock, exclusion, and budget policy rechecks the selected cart before checkout. Fractional quantities are rejected rather than rounded down.

Plan metadata reports `planner.engine: local-tfidf-knn-v1` in local mode and `external-structured-model` for the optional adapter. Local mode performs no AI-related network request.

## Reproducible evaluation

Run from the repository root:

```sh
python3 -m unittest tests/test_planner.py -v
```

The held-out classification test covers 16 exact phrases absent from the training corpus, with four each for pump, battery, tools, and unsupported requests. The observed result is **16/16 on this small synthetic test set**. The tests also exercise alternatives, quantities and surplus disclosure, excluded conditions, negated goals, multiple categories, supplier fallbacks, written versus structured budgets, partial-cart rejection, out-of-bounds numbers, synthetic compatibility evidence, inventory fallbacks, and invalid external-model proposals. This is regression evidence for the bounded demo, not a benchmark against competing systems or a claim about real-user accuracy.

The training corpus is original synthetic work under Apache-2.0. [`data/README.md`](../data/README.md) documents its provenance and limits. No real users, revenue, provider transactions, or live integrations are fabricated as evaluation evidence.
