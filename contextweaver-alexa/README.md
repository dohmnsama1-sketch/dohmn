# ContextWeaver — Inspectable ambient intelligence for Alexa+

ContextWeaver is a privacy-first ambient orchestration prototype for the Amazon Alexa+ track. It turns an explicit natural-language request into a selective context receipt, a constraint-safe action graph, and a machine-readable explanation for every proposed action.

**Live demo:** https://contextweaver-alexa.floot.app/

## What is in this source snapshot

This directory contains the original application-specific MCP endpoint, web-client integration helper, and regression tests exported from the canonical Floot project `1f21575a-0820-4bf2-971e-c039838d726b` at source version `1792256704025`.

The visual shell is hosted and built by Floot. Seeded platform UI-kit files are intentionally not republished here. The exported files are the authored competition logic and tests used by the live demo.

## Trust model

- Explicit demo input only: no claimed Alexa+ preview SDK, calendar, memory, or hidden personal data access.
- No external writes in the demonstrated action graph.
- Every action is reversible and has an explanation receipt.
- The scheduler preserves the exact approved minute budget.
- Same-origin enforcement and MCP protocol-version checks fail closed.

## MCP surface

The live `POST /_api/mcp` endpoint implements MCP protocol `2025-11-25` with three deterministic tools:

1. `weave_context`
2. `build_action_graph`
3. `explain_action`

## Verified production scenario

Input:

> Plan my next 1 hour and 30 minutes. I need to leave by 9:00 PM.

Observed on 17 October 2026 after deployment:

- parsed budget: 90 minutes
- planned budget: 90 minutes
- departure constraint: 21:00
- action nodes: 4
- explanation receipts: 4/4
- external writes: 0
- result: budget-safe

## Important status boundary

This public source snapshot is a required submission asset. It is **not** an organizer submission receipt, acceptance, award, payable amount, or cash settlement. Registration, required entrant attestations, product feedback, the public English video, and final Devpost submission remain separate steps.
