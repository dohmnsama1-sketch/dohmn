# Reproducible synthetic intent evaluation

This evaluation exports the **existing 16 synthetic regression phrases** into a scored, inspectable report. It does not introduce a new benchmark or broaden the test suite. The classifier and training corpus are unchanged.

## Run it

From the project root, with Python 3.11 or later:

```sh
python3 tools/evaluate_intents.py
```

The default output is [`evaluation/intent-report.json`](evaluation/intent-report.json). A different output file can be chosen with `--output path/to/report.json`. The command exits with status `0` if every phrase matches its expected intent, `1` if at least one result fails, and `2` if source/split validation fails. It refuses to overwrite its source inputs.

The tool reads `LearnedIntentTests.CASES` as literal data from `tests/test_planner.py`, without importing or running those tests. It constructs the application's `IntentModel` from the committed training corpus and evaluates only that class. It loads no `.env` and uses no external AI adapter, HTTP server, PayPal API, or approval/capture flow. Python socket construction, DNS resolution, and connection helpers are blocked during inference so unintended network use fails.

## Actual observation — 5 October 2026

The saved report was generated locally on Python 3.12. It contains the runtime version and source hashes. The observed results are:

| Expected intent | Cases | Correct |
| --- | ---: | ---: |
| Pump | 4 | 4 |
| Battery | 4 | 4 |
| Tools | 4 | 4 |
| Unsupported | 4 | 4 |
| Total | 16 | 16 |

All 12 supported phrases were accepted. All 4 unsupported phrases were rejected, with **0 false acceptances in those four cases**. These are counts for this set only. They are not estimates of accuracy on arbitrary shopping requests.

The report includes the complete confusion matrix, per-class counts/precision/recall, each exact evaluation phrase, its expected/predicted class, acceptance decision, similarity, margin, and three nearest training examples. Similarity and margin are retrieval scores, not confidence probabilities.

## Provenance and integrity

The original synthetic training corpus has 72 phrases, 18 per class. The evaluation phrases were also authored for this project and have been used in development. This is **not** an independent or blinded assessment.

The report pins SHA-256 hashes for the training file, classifier file, complete test source file, and extracted case list. Training/evaluation exact overlap is checked after case folding, punctuation removal, and whitespace normalization. Duplicate normalized evaluation phrases also cause failure rather than inflating the denominator.

No normalized phrase overlap was found in this run. That does not rule out shared vocabulary, paraphrases, or semantic templates between the training and evaluation sets. The nearest-example traces deliberately make such relationships visible.

A targeted integrity check regenerated the report and obtained identical bytes on the same interpreter/checkout, checked that the confusion matrix accounts for all 16 phrases, and confirmed that a copied training/evaluation phrase and a duplicate evaluation phrase are rejected even after case/punctuation changes. No provider or external model call occurred. Across different Python versions, runtime metadata can differ; compare source hashes, predictions, and metrics rather than expecting an identical whole-file hash.

## What this establishes

This is reproducible evidence that the committed local classifier produces the reported decisions on a small English synthetic regression set. It does not evaluate the full planner, multi-goal parsing, cart policy, mechanical compatibility, battery safety, live stock, merchant fulfillment, real users, or PayPal execution. The existing cart/checkout tests cover separate local and mocked-provider behavior; they were not rerun or counted as new evidence in this evaluation.

Provider-confirmed PayPal sandbox order, payer approval, and capture evidence remains pending. No payment or revenue claim follows from the report. See [`PAYPAL_SANDBOX.md`](PAYPAL_SANDBOX.md) for that independent integration check.
