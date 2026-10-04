# Verification — 4 October 2026

The combined suite passed **62 tests** on Python 3.12. This includes local HTTP behavior, learned intent inference, cart constraints, explicit negation and replacement requests, session ownership, read-only preview, provider approval checks, amount matching and idempotent retries. JavaScript syntax was checked separately.

PayPal provider responses were mocked in tests. No external PayPal order, payer approval or capture has been executed. Sandbox credentials are absent. The optional external AI adapter has not been exercised with a model service.

The working browser application was exercised for:

- Pump repair at a $120 ceiling: one $24 synthetic repair kit, with the $94 replacement kept outside the cart.
- A $10 ceiling: checkout blocked, with the failed boundary visible.
- “Replace the water pump. Do not buy a repair kit.”: one $94 replacement; explicit instructions override the preference.
- Read-only checkout preview: exact canonical payload shown, with no approval recorded or PayPal request made.
- Model trace: disclosed training examples and similarity evidence shown.

The 16 held-out synthetic intent phrases passed 16/16. This is a small regression set, not a production accuracy or customer benchmark.

The [public source repository](https://github.com/dohmnsama1-sketch/dohmn) contains all source, the corpus, tests, setup documentation and Apache-2.0 license. [CI completed successfully on Python 3.11 and 3.12](https://github.com/dohmnsama1-sketch/dohmn/actions/runs/37194002389).

The local 2:15 engineering preview passed a complete media decode check. It uses actual captured application screens and an offline synthetic voice. It explicitly discloses pending sandbox execution.

Outstanding submission evidence: actual PayPal sandbox execution; final public video showing the completed integration; factual registration/eligibility answers; provider-confirmed submission. No cash award or payable entitlement exists yet.
