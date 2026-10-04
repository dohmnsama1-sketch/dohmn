# MendCart submission draft

Use this copy only with the final verified implementation. The complete public repository and public engineering preview exist. Registration, actual sandbox execution, the final integration video and final entry remain pending.

## Name and tagline

**MendCart**

Repair before replace: an AI procurement plan with an authorized PayPal sandbox checkout.

## Inspiration

A shared workshop makes a consequential decision when equipment fails: buy a replacement, repair it, or pause because the evidence and budget do not support either choice. MendCart makes that decision visible before a payment is prepared.

## What it does

MendCart turns a maintenance request into a constrained cart in a synthetic repair catalog. The buyer inspects the recommendation, quantity, supplier eligibility and total. Policy failures block checkout. Authorization is bound to the server's stored plan; PayPal sandbox provides order creation, buyer approval and capture.

Its intended audience is a shared workshop or repair team. Catalog data are illustrative. The project does not claim real inventory, supplier verification, customers or revenue.

## How it is built

The app uses Python's standard library and a browser interface. Its default AI is a supervised TF-IDF nearest-neighbor classifier trained from an original synthetic corpus. It identifies a supported maintenance intent used by the constrained cart optimizer. Model evidence and limits are documented in the source.

PayPal Orders v2 is the sandbox payment component. The backend stores the approved plan in the browser session and computes the order from canonical items. After buyer approval, it verifies provider state and captures. Stable provider request identifiers limit duplicate requests within the process.

An optional OpenAI-compatible adapter is included. List an external model as used only if that mode was actually exercised. AI-assisted software development was used.

## Lessons and next steps

Model output, client totals and the buyer's authorized cart have different roles. Binding authorization to the server's plan makes the commerce path explainable.

Next steps are real compatibility and supplier evidence, persistent records and buyer identity, then evaluation with workshops. These are future work.

## Main technology answer: 28784

Use only after the actual sandbox walkthrough is evidenced:

> PayPal Orders v2 in the free sandbox environment creates a plan-bound order, hands the buyer to PayPal for approval, and captures after the backend verifies approved provider state. MendCart's local supervised TF-IDF nearest-neighbor classifier learns from an original synthetic maintenance corpus and identifies the request used by a constrained cart planner. Catalog and budget policy revalidate model output; buyer authorization is recorded separately. The final video demonstrates the application and actual sandbox flow.

Without actual capture evidence, keep this stage pending rather than claiming demonstrated completion.

## Required form mapping

Form read on 4 October 2026. Fetch current requirements again before writing.

| ID | Field | Prepared answer or required fact |
|---|---|---|
| 28778 | Submitter type | Actual Individual / Team / Organization |
| 28779 | Residence | Actual country; Saudi Arabia offered |
| 28780 | Canadian province | Actual province or `N/A` |
| 28781 | Organization | Actual organization or `N/A` |
| 28782 | New/existing | `New` for the 4 October start |
| 28783 | Prior changes | `N/A` if new |
| 28784 | PayPal + AI use | Verified technology description |
| 28786 | Sponsors | Only actually used tools; current local stack: `None, used other AI tools.` |
| 28788 | GitHub | https://github.com/dohmnsama1-sketch/dohmn — complete public source and Apache-2.0 license |
| 28787 | Demo URL | Optional tested hosted URL |
| 28798 | Testing | README plus sandbox guide; no secrets |
| 28790 | PayPal rating | Accurate 1–10 assessment after integration |
| 28791 | Feedback | Observations from actual development/testing |
| 28792 | Contact preference | Actual Yes / No |
| 28794 | Age | Entrant/team of legal majority where resident |
| 28795 | Jurisdiction | Accurate eligible jurisdiction attestation |
| 28796 | Employment | Accurate sponsor/administrator affiliation attestation |

The global project form also requires the write-up and **public YouTube URL**. The current [engineering preview](https://youtu.be/kqcYwCBVv50) is public and under three minutes, but does not demonstrate an executed sandbox integration. Replace it with the final integration recording before claiming that the complete sandbox flow is demonstrated. Optional sponsor feedback should be answered only for used tools.

## Registration facts

The connected account has complete required name fields. Unknown experience and eligibility facts must stay accurate.

| ID | Question | Answers |
|---|---|---|
| 4402 | Prior payment integration | Yes / No / Not Sure |
| 4403 | PayPal before this hackathon | Yes / No / Not Sure |
| 4405 | AI experience | Beginner / Intermediate / Expert |
| 4406 | Goal | Learning / Prizes / Career Growth / Providing Product Feedback / Exposure / Solving a Problem; multiple allowed |
| 4424 | Sponsor marketing | Yes / No |

Team preference: Working solo / Looking for teammates / Already have a team. Referral survey is optional. Broad execution authorization does not supply unknown factual answers about age, residence, experience, identity or affiliations.

Agreements: [official rules](https://paypalaihackathon.devpost.com/rules) and [Devpost terms](https://info.devpost.com/terms). Eligibility text: “Above legal age of majority in country of residence / All countries/territories, excluding / standard exceptions”.

## Evidence to retain

Public repository URL and exact source revision; public video URL and duration; current tests; sanitized actual sandbox order/capture evidence; registration confirmation; final submitted entry receipt. Keep secrets, buyer credentials and personal attestations out of public source.
