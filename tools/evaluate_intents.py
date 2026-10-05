#!/usr/bin/env python3
"""Export the existing synthetic holdout as an auditable offline AI report.

Uses the same classifier class as the application. No API adapter, .env,
HTTP server, PayPal action, or external model is invoked.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import re
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mendcart.planner import IntentModel, _MODEL_VERSION  # noqa: E402

LABELS = ("pump", "battery", "tools", "unsupported")
CORPUS_PATH = ROOT / "data" / "intent_corpus.json"
EVALUATION_PATH = ROOT / "tests" / "test_planner.py"
MODEL_PATH = ROOT / "mendcart" / "planner.py"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(text: str) -> str:
    """Check exact/near-exact wording overlap; not semantic independence."""
    return " ".join(re.findall(r"\w+", text.casefold()))


def committed_cases(path: Path = EVALUATION_PATH) -> list[tuple[str, str]]:
    """Read the existing test literals without running/importing test code."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "LearnedIntentTests":
            for statement in node.body:
                if isinstance(statement, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "CASES" for target in statement.targets
                ):
                    cases = ast.literal_eval(statement.value)
                    if not isinstance(cases, list) or not cases:
                        raise ValueError("The committed holdout must contain a nonempty case list.")
                    return cases
    raise ValueError("Cannot locate the committed LearnedIntentTests.CASES holdout.")


def validate_split(examples: list[dict], cases: list[tuple[str, str]]) -> dict:
    training_texts = set()
    for row in examples:
        if row.get("intent") not in LABELS or not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError("Training examples must have known labels and nonempty text.")
        training_texts.add(normalized(row["text"]))
    seen = set()
    for case in cases:
        if not isinstance(case, (list, tuple)) or len(case) != 2:
            raise ValueError("Every evaluation case must be a text/expected-label pair.")
        text, expected = case
        if not isinstance(text, str) or not text.strip() or expected not in LABELS:
            raise ValueError("Evaluation cases must have known labels and nonempty text.")
        key = normalized(text)
        if key in seen:
            raise ValueError("Evaluation has a duplicate normalized phrase; report refused.")
        if key in training_texts:
            raise ValueError("Training and evaluation share a normalized phrase; report refused.")
        seen.add(key)
    return {"exact_or_normalized_phrase_overlap": 0,
            "duplicate_evaluation_phrases": 0,
            "normalization": "Unicode casefold, word tokens, whitespace/punctuation normalization",
            "semantic_independence_established": False,
            "note": "Distinct strings do not establish a blind or independently authored test set."}


def evaluate() -> dict:
    corpus_bytes = CORPUS_PATH.read_bytes()
    corpus = json.loads(corpus_bytes)
    examples = corpus["examples"]
    cases = committed_cases()
    split = validate_split(examples, cases)
    # Any accidental network use introduced by a future model change fails.
    offline_error = RuntimeError("Evaluation is offline; network access is disabled.")
    with patch.object(socket, "socket", side_effect=offline_error), \
            patch.object(socket, "getaddrinfo", side_effect=offline_error), \
            patch.object(socket, "create_connection", side_effect=offline_error):
        model = IntentModel(examples)
        results = []
        matrix = {expected: {predicted: 0 for predicted in LABELS} for expected in LABELS}
        for number, (text, expected) in enumerate(cases, 1):
            inference = model.classify(text)
            predicted = inference["intent"]
            matrix[expected][predicted] += 1
            results.append({"case_id": f"existing-holdout-{number:02d}", "text": text,
                            "expected": expected, "predicted": predicted,
                            "correct": expected == predicted, "accepted": inference["accepted"],
                            "similarity": inference["similarity"], "margin": inference["margin"],
                            "nearest_training_examples": inference["matches"]})
    count = len(results)
    correct = sum(case["correct"] for case in results)
    supported = [case for case in results if case["expected"] != "unsupported"]
    unsupported = [case for case in results if case["expected"] == "unsupported"]
    per_class = {}
    for label in LABELS:
        expected_count = sum(matrix[label].values())
        predicted_count = sum(row[label] for row in matrix.values())
        true_positive = matrix[label][label]
        per_class[label] = {"expected_count": expected_count, "predicted_count": predicted_count,
                            "correct_count": true_positive,
                            "precision": true_positive / predicted_count if predicted_count else None,
                            "recall": true_positive / expected_count if expected_count else None}
    case_bytes = json.dumps(cases, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": 1,
        "experiment": "existing-16-phrase-synthetic-intent-regression",
        "engine": _MODEL_VERSION,
        "scope": "Single-clause intent classification only; not cart-policy, compatibility, commerce, or real-user evaluation.",
        "execution": {"python": platform.python_version(), "network_disabled": True,
                      "external_model_used": False, "paypal_called": False, "dotenv_loaded": False},
        "sources": {
            "training": {"path": "data/intent_corpus.json", "sha256": sha256(corpus_bytes),
                         "examples": len(examples), "label_counts": dict(sorted(Counter(row["intent"] for row in examples).items())),
                         "provenance": corpus.get("provenance"), "license": corpus.get("license")},
            "evaluation": {"path": "tests/test_planner.py:LearnedIntentTests.CASES",
                           "source_file_sha256": sha256(EVALUATION_PATH.read_bytes()),
                           "case_list_sha256": sha256(case_bytes), "examples": count,
                           "provenance": "Existing original synthetic regression phrases authored for this project; not independent real-user data."},
            "classifier": {"path": "mendcart/planner.py", "sha256": sha256(MODEL_PATH.read_bytes())},
        },
        "split_checks": split,
        "metrics": {"correct": correct, "total": count, "accuracy_on_this_set": correct / count,
                    "supported_requests": len(supported),
                    "supported_requests_accepted": sum(case["accepted"] for case in supported),
                    "unsupported_requests": len(unsupported),
                    "unsupported_requests_rejected": sum(not case["accepted"] for case in unsupported),
                    "unsupported_false_accepts": sum(case["accepted"] for case in unsupported),
                    "confusion_matrix_rows_expected_columns_predicted": matrix, "per_class": per_class},
        "limitations": [
            "Small, project-authored synthetic set; regression evidence only.",
            "No independent, blinded, multilingual, adversarial, or real-user performance estimate.",
            "Training/evaluation phrases can share vocabulary and semantic templates despite no exact overlap.",
            "Similarity and margin are retrieval scores, not calibrated probabilities.",
            "A correct intent does not establish safe battery use, real pump compatibility, a valid cart, or provider payment success.",
        ],
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "evaluation" / "intent-report.json")
    args = parser.parse_args()
    protected = {CORPUS_PATH.resolve(), EVALUATION_PATH.resolve(), MODEL_PATH.resolve(), Path(__file__).resolve()}
    if args.output.resolve() in protected:
        parser.error("The evaluation report must not overwrite a source file.")
    try:
        report = evaluate()
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        print(f"Evaluation report not created: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    metrics = report["metrics"]
    print(f"Synthetic intent regression: {metrics['correct']}/{metrics['total']}; unsupported false accepts: {metrics['unsupported_false_accepts']}/{metrics['unsupported_requests']}.")
    print(f"Report: {args.output}")
    return 0 if metrics["correct"] == metrics["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
