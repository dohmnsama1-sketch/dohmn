# Verification

## 21 October 2026 — request exclusions

Fixed a request-parser defect where a negative clause such as `Avoid batteries` or `Exclude tools` was skipped without excluding that category's SKUs. A later conflicting purchase could therefore pass policy. Bare category exclusions now constrain all alternatives, including when they precede or follow the positive request. A contradictory cart is blocked in full. Battery-condition exclusions remain distinct: `avoid new cells` still permits reclaimed cells, while `avoid reclaimed cells` still permits new cells. Whole-pump category exclusions are limited to a bare pump phrase so component and replacement constraints keep their existing behavior.

The local suite passed **72 tests** on Python 3.12, including six new regression methods covering category conflicts, unrelated goals, singular/plural nouns, word boundaries, battery conditions and a mocked external adapter trying to override exclusions. The six methods were first run against the old implementation and exposed 41 failing subcases. The original synthetic intent regression remains 16/16 with 0/4 unsupported false accepts; the classifier and its 72-example corpus did not change. These are project-authored development regressions, not an independent accuracy benchmark.

All provider responses in the checkout tests were mocked; this repair did not create, approve or capture a PayPal order. Actual sandbox execution, registration, the final integration video and competition submission remain pending. Publication and deployment must be verified separately from these local checks.

## Pending capture refresh — 7 October 2026

The full local suite passed **66 tests** on Python 3.12 after the pending-capture fix. Four new HTTP tests cover a pending result remaining pending and then becoming completed, foreign-session rejection before provider access, failed-refresh recovery, eight mismatched response variants, and terminal declined-result idempotency. They verify that retries issue provider GETs, preserve the original capture ID and amount, and never submit a second capture. Failed validation leaves the previous cache and audit untouched.

All provider responses in this check were mocked. No actual PayPal order, approval or capture occurred. JavaScript syntax and the Git whitespace check passed. The interface now distinguishes actual pending captures from known terminal non-success outcomes. Terminal caches do not monitor later refund or dispute changes; state is still in memory.

## Original working application — 4 October 2026

The combined suite passed **62 tests** on Python 3.12. This includes local HTTP behavior, learned intent inference, cart constraints, explicit negation and replacement requests, session ownership, read-only preview, provider approval checks, amount matching and idempotent retries. JavaScript syntax was checked separately.

PayPal provider responses were mocked in tests. No external PayPal order, payer approval or capture has been executed. Sandbox credentials are absent. The optional external AI adapter has not been exercised with a model service.

The working browser application was exercised for:

- Pump repair at a $120 ceiling: one $24 synthetic repair kit, with the $94 replacement kept outside the cart.
- A $10 ceiling: checkout blocked, with the failed boundary visible.
- “Replace the water pump. Do not buy a repair kit.”: one $94 replacement; explicit instructions override the preference.
- Read-only checkout preview: exact canonical payload shown, with no approval recorded or PayPal request made.
- Model trace: disclosed training examples and similarity evidence shown.

The 16 project-authored synthetic intent phrases passed 16/16. This is a small regression set used during development, not an independent, production accuracy or customer benchmark. The [reproducible report](EVALUATION.md) was added on 5 October; the classifier and corpus were not changed by the capture fix.

The [public source repository](https://github.com/dohmnsama1-sketch/dohmn) contains all source, the corpus, tests, setup documentation and Apache-2.0 license. [CI completed successfully on Python 3.11 and 3.12](https://github.com/dohmnsama1-sketch/dohmn/actions/runs/37194002389).

The approximately 2:15 engineering preview passed a complete media decode check and was [published publicly on YouTube](https://youtu.be/kqcYwCBVv50) on 4 October 2026. YouTube Studio confirmed publication after copyright and Community Guidelines checks reported no issues. It uses actual captured application screens and an offline synthetic voice, disclosed in the description and upload settings. It explicitly discloses pending sandbox execution. Public preview publication does not establish a completed integration or contest entry.

Outstanding submission evidence: actual PayPal sandbox execution; final public video showing the completed integration; factual registration/eligibility answers; provider-confirmed submission. No cash award or payable entitlement exists yet.
