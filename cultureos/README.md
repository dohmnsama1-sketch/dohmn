# CultureOS

**CultureOS is a Qloo-grounded cultural launch intelligence agent.** It takes a product or brand brief, a target market, and a small set of cultural anchors, resolves those anchors against Qloo, maps cross-domain affinities, and stress-tests whether the strongest signals survive when one anchor is removed.

This is intentionally not an LLM wrapper. The core product value comes from Qloo's taste graph and a transparent orchestration layer that exposes where each recommendation came from.

## Why this needs Qloo

A generic language model can invent culturally plausible associations. CultureOS instead:

1. resolves named cultural seeds against Qloo entity search;
2. resolves the target market to a Qloo locality when possible;
3. queries Qloo Insights across brands, places, artists, movies, and destinations;
4. builds cross-domain cultural bridges only from returned Qloo entities;
5. runs a counterfactual stability check by removing one seed at a time and measuring shortlist retention;
6. returns an evidence trace and explicit limitations.

If Qloo cannot resolve the seeds, CultureOS fails visibly rather than fabricating an answer.

## Responsible data handling

CultureOS does **not** need names, emails, device identifiers, account IDs, location histories, health data, financial data, or other personal data. Inputs are product concepts, a market name, and public cultural entities.

Qloo results are presented as aggregate affinities. They are not described as causal evidence or predictions about an individual.

## Setup

Requirements:

- Node.js 22+
- Qloo hackathon API key

```bash
cd cultureos
npm install
cp .env.example .env.local
npm run dev
```

Environment variables:

```text
QLOO_API_KEY=...
QLOO_BASE_URL=https://hackathon.api.qloo.com
```

The event credential must remain server-side. Never place it in browser code, public source control, screenshots, demo recordings, or logs.

## Verification

```bash
npm run typecheck
npm test
npm run build
```

The automated tests use a fake taste-graph client. They verify orchestration logic without publishing Qloo data or consuming event quota.

## Submission quality gate

The Devpost entry is not ready until all of these are true:

- the event-issued Qloo key is exercised against the hackathon base URL;
- live Search and Insights response parsing is verified;
- typecheck, tests, and production build pass;
- the public deployment works end-to-end without private access;
- rate-limit, timeout, invalid-seed, and provider-error states are checked;
- no secret appears in the client bundle, git history, logs, screenshots, or docs;
- Qloo provenance and limitations remain visible;
- mobile and desktop UX are manually checked;
- clean-environment reproduction succeeds;
- all submission claims are backed by reproducible evidence.

## License

Apache License 2.0 — see the repository root `LICENSE`.
