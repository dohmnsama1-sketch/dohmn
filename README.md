# MendCart

**Repair before replace. A purchase plan with a spending boundary.**

MendCart helps a shared workshop turn a maintenance request into a repair or replenishment cart. A local machine learning model identifies the request, a constrained planner compares eligible catalog options, and a buyer reviews the resulting items and budget. The server binds that authorization to an immutable plan before handing it to PayPal sandbox checkout.

Built for the **PayPal AI Hackathon 2026**, with a focus on Best Use of PayPal + AI and Best Use of Agentic Commerce. Entry, selection and prizes are separate milestones; this repository does not claim an award or revenue.

## Run the application

Requirements: **Python 3.11+** and a browser. The application and default local model use the Python standard library. No Python package installation, external model account or paid inference is required.

From the repository root:

```sh
cp .env.example .env
python3 -m mendcart.app
```

Open **http://127.0.0.1:8000**. Opening `web/index.html` directly as a file does not run the backend. Existing environment variables take precedence over `.env`.

Try `Our workshop's water pump is leaking. Try a repair before replacing it.` with a $120 budget. Repeat with a $10 budget to see checkout blocked. Battery and repair tools requests explore other supported catalog examples.

Review the plan, check the approval box and continue. Without PayPal credentials, the app returns a clearly labeled **preview** and creates no PayPal order. Actual creation and capture require a sandbox developer app and sandbox buyer approval.

## What AI does

The default AI is a supervised **TF-IDF nearest-neighbor intent classifier**, trained at runtime from an original synthetic corpus bundled in `data/intent_corpus.json`. It classifies requests within the demo's narrow maintenance domain. A constrained optimizer then applies quantities, repair preferences, catalog eligibility and budget policy to prepare the cart. Unknown or insufficiently supported requests are blocked.

This is a local machine learning model, not a pretrained language model or a claim of general repair expertise. The corpus contains authored examples, not customer records. Its role, limits and evaluation are described in [docs/AI.md](docs/AI.md). Synthetic example performance does not establish production accuracy.

An optional OpenAI-compatible chat model adapter can propose a plan. Configure `OPENAI_BASE_URL`, `OPENAI_API_KEY` and `OPENAI_MODEL` for that mode. The selected endpoint may have fees. Generated SKUs and quantities are revalidated against catalog and policy; model output never authorizes spending.

## What PayPal does

PayPal **Orders v2 in sandbox** provides the commerce flow:

1. The buyer authorizes a server-held plan in the current browser session.
2. The server creates an order with the cart's canonical amount and item totals.
3. The buyer approves it on PayPal's sandbox page.
4. On return, MendCart verifies provider state and captures only an approved order bound to that session and plan.
5. The interface displays sandbox status and the recorded event sequence.

Set `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` in `.env` from a **sandbox** developer app. Keep `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`. `MENDCART_PUBLIC_URL` controls the return origin; its default is `http://127.0.0.1:8000`. Public return origins require HTTPS. See [docs/PAYPAL_SANDBOX.md](docs/PAYPAL_SANDBOX.md).

The code contains a sandbox integration; successful provider execution must be established separately. A preview, unit test or mocked response is not evidence of a completed PayPal sandbox transaction.

## A reviewable spending boundary

The backend stores immutable plans, explicit authorization, owned order references and audit events in memory. Client-supplied prices and policy results do not control the order. Plans expire after 30 minutes. Repeated provider requests use stable request identifiers within the demo process.

State belongs to the current browser session. Restarting the server clears it. This hackathon prototype has no durable database, production identity system or live payment mode. The buyer approval controls are part of the product workflow.

## Data and claims

All catalog items, suppliers, stock, prices and evidence text are **synthetic demo fixtures**. They do not establish compatibility, supplier reputation, live availability, measured savings or environmental impact. No live shopping integration, customers, revenue or user research is represented.

AI-assisted development was used. The original training examples and source are included under Apache-2.0. Optional remote models remain subject to their providers' terms.

## Verify locally

```sh
python3 -m unittest discover -s tests -v
```

The suite uses local fixtures and mocked provider transport. It verifies program behavior; it does not contact PayPal or establish provider acceptance. Follow the sandbox guide for a separate provider walkthrough.

## Submission materials

- [Competition requirements and current readiness](docs/COMPETITION.md)
- [Submission draft and form fields](docs/SUBMISSION.md)
- [Demo recording script](docs/DEMO_SCRIPT.md)

A **public GitHub repository**, a **public YouTube video shorter than three minutes**, and an actual sandbox demonstration remain final entry requirements. Pending stages are tracked in the competition document.

## License

[Apache-2.0](LICENSE).
