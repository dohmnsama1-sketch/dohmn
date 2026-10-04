# Original synthetic intent corpus

`intent_corpus.json` contains 72 original synthetic training phrases: 18 each for pump, battery, tools, and unsupported/ambiguous requests. The examples were authored for MendCart and contain no customer messages, scraped content, payments, personally identifying information, or observed usage.

The corpus is licensed under the repository's Apache-2.0 license. Its provenance is also recorded inside the JSON file. It trains a small supervised TF-IDF nearest-neighbor intent model locally at first use. It is not an externally pretrained language model or evidence of real customer research.

The held-out evaluation strings are committed separately in `tests/test_planner.py`; none of those exact strings is in this training file. The dataset and test set are both small synthetic sets authored for the demo. The resulting accuracy is not a production benchmark or an estimate of performance on real users.
