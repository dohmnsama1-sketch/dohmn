# PayPal sandbox flow and verification

MendCart uses PayPal Orders v2 with the API origin restricted to exactly `https://api-m.sandbox.paypal.com`. Alternate hosts, live hosts, non-HTTPS API URLs, user information, paths, and extra ports are rejected. API redirects are rejected before credentials can be forwarded. PayPal payer links must also belong to a PayPal sandbox origin.

A working local preview does **not** establish that PayPal has issued an order or accepted a capture. This repository has automated mocked provider tests. The real sandbox flow must be recorded separately after developer credentials are available. Sandbox balances and captures are test data, never revenue.

## Configure and run

1. Create or select a PayPal Developer **sandbox** application and a separate sandbox buyer account. Developer account identity or legal declarations must be supplied truthfully by the account holder.
2. Copy `.env.example` to `.env` in the project root and set its sandbox `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`. Keep the file private; it is excluded from Git. `.env` is parsed as literal configuration and is never executed as a shell script. Existing process environment variables take precedence.
3. Keep `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`.
4. Start `python -m mendcart.app` and open `http://127.0.0.1:8000/` in one browser session. `PORT` and `MENDCART_HOST` optionally change the listen address. The default bind address is loopback.
5. `MENDCART_PUBLIC_URL` optionally sets the **origin only**, such as `http://127.0.0.1:8000` or an HTTPS deployment origin. It must match the URL you use in the browser. HTTP is permitted only for loopback origins. A public deployment requires HTTPS and additional operational controls; this demo is not a production payment service.

Never copy secrets into a video, screenshot, issue, chat, public repository, or exported plan. No client secret or access token is sent to the browser. The `/api/status` response reveals only configuration presence, provider mode, model mode, and synthetic catalog disclosure.

## Browser flow

1. Describe the repair or procurement task and choose a budget and supplier policy.
2. The server builds the plan, keeps an immutable copy of its items and original budget policy, and issues an opaque `plan_id`. The browser receives a readable plan plus a 30-minute expiry and the decision trace. All suppliers, prices, stock, and catalog evidence are synthetic fixtures.
3. Review the plan and approve its exact server-held amount. Approval is recorded against this plan and the browser's HttpOnly session cookie. Changing the request requires a newly generated plan and approval. It cannot silently change an existing approval.
4. Create the sandbox order. The server rechecks catalog rows, quantities, supplier restrictions, and the original budget. Browser-supplied `plan`, amount, or policy fields are ignored. The Orders v2 payload includes item prices and a matching `amount.breakdown.item_total`.
5. When credentials are absent, the result is explicitly `sandbox_preview`, `credentials_missing`, with no real provider order ID or payer link. The payload shown is an unsubmitted preview.
6. When credentials are configured, the server exchanges the sandbox application credentials for an OAuth access token, then creates a sandbox order. Each plan has stable UUID request IDs for creation and capture. Retrying the same plan or order reuses its request ID and its recorded result.
7. Follow the returned `approval_url` and approve using the sandbox buyer account. The provider returns to `/?paypal=return&token=<order_id>` or cancels at `/?paypal=cancel&token=<order_id>`. Returning to MendCart is not itself proof of payer approval.
8. MendCart retrieves the order from PayPal, validates its stored plan reference and amount, and permits capture only when the provider reports `APPROVED`. A browser `payer_approved` flag has no authority. A previously `COMPLETED` order is recovered without issuing a second capture.
9. The browser receives a minimal order/capture summary and chronological local events. Provider payer email/name fields and raw provider error bodies are excluded.

## HTTP contract

Use the same browser cookie jar throughout. Foreign sessions cannot view, approve, or capture another session's plan/order. POST requests from a foreign origin or mismatched host are rejected.

| Endpoint | Input | Result |
| --- | --- | --- |
| `GET /api/status` | none | Sandbox configuration presence, actual model mode, synthetic disclosure |
| `GET /api/health` | none | Local demo health |
| `GET /api/catalog` | none | Synthetic catalog |
| `POST /api/plan` | `request`, `max_budget`; optional planner policy fields | Plan plus `plan_id`, `expires_at`, `approval_recorded`, `events` |
| `GET /api/plans/{plan_id}` | session cookie | Owned plan snapshot and events |
| `GET /api/plans/{plan_id}/preview` | session cookie | Read-only canonical checkout payload; no approval, provider calls, or state changes |
| `POST /api/plans/approve` | `plan_id`, `human_approved: true` | Recorded approval for that server plan |
| `POST /api/paypal/orders` | `plan_id`; optionally `human_approved: true` to approve and create in one operation | `mode`, `status`, `plan_id`, `order_id`, `approval_url`, `amount`, `currency`, `events`; preview includes unsubmitted `order` |
| `GET /api/paypal/orders/{order_id}` | session cookie | Fresh provider status after reference/amount verification, plus owned `plan` for return recovery |
| `POST /api/paypal/capture` | `order_id` | Server-verified provider capture or prior completed result; minimal `capture` summary |

Plan/order ownership, approval events, and captured results are **in memory**. Restarting the demo clears these records; the server then refuses unknown old order IDs rather than capturing arbitrary external orders. Sessions and plans have bounded demo capacity. There is no durable ledger, webhook reconciliation, stock reservation, merchant fulfillment, or live catalog feed. Provider idempotency has provider-specific retention limits; do not treat this local store as a permanent financial ledger.

## Automated evidence and remaining provider check

`python -m unittest tests.test_checkout -v` runs a real ephemeral localhost HTTP server, with all PayPal responses mocked. It tests immutable server totals, policy failure, expiry, browser ownership, cross-origin rejection, forged payer flags, provider amount mismatches, idempotent create/capture, interrupted capture recovery, OAuth headers/cache, sanitized provider errors, exact sandbox origins, return URLs, and Orders v2 item-total consistency.

Before describing the integration as provider-verified, run the browser flow with genuine sandbox credentials and preserve: sandbox order ID/status, provider-approved status, completed sandbox capture ID/status, matching USD amount, and a redacted screenshot or short video. Do not publish the buyer's personal details or any credentials.

Official references: [Orders v2](https://developer.paypal.com/api/orders/v2), [OAuth authentication](https://developer.paypal.com/api/rest/authentication/), and [PayPal request idempotency](https://developer.paypal.com/api/rest/reference/idempotency/).
