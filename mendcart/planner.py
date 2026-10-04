"""Learned intent retrieval, evidence-bound cart optimization, and payment policy.

The default AI is a supervised TF-IDF nearest-neighbor model, not an LLM.
It trains on the committed synthetic corpus without network calls or API keys.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import product
from math import ceil, isfinite, log, sqrt
from pathlib import Path
import json
import os
import re
from urllib.request import Request, urlopen

from .catalog import CATALOG, approved_by_sku


@dataclass
class PlanRequest:
    request: str
    max_budget: float
    currency: str = "USD"
    allowed_suppliers: list[str] = field(default_factory=lambda: ["greenloop-demo", "recell-demo", "fixfirst-demo"])
    approval_required: bool = True
    repair_first: bool = True

    def __post_init__(self):
        if not isinstance(self.request, str) or not 5 <= len(self.request) <= 500:
            raise ValueError("Request must contain between 5 and 500 characters.")
        if isinstance(self.max_budget, bool) or not isinstance(self.max_budget, (int, float)) or not isfinite(self.max_budget) or not 0 < self.max_budget <= 300:
            raise ValueError("Budget must be greater than zero and at most $300.")
        if not isinstance(self.allowed_suppliers, list) or any(not isinstance(x, str) for x in self.allowed_suppliers):
            raise ValueError("Allowed suppliers must be a list of supplier identifiers.")


@dataclass
class RequestedItem:
    sku: str
    quantity: int = 1


@dataclass
class AgentPlan:
    summary: str
    items: list[RequestedItem]
    reasoning: str
    candidates: list[dict] = field(default_factory=list)
    decision_trace: list[dict] = field(default_factory=list)
    policy_findings: list[str] = field(default_factory=list)
    requirements: list[dict] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    engine: str = "external-structured-model"


_STOPWORDS = set("a an the my our i we need want please for to of is are it its have has me us with some get buy find source procure purchase supply choose select would should can must this that from at in on as be using use".split())
_NUMBER_WORDS = {word: i for i, word in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
_NUMBER_WORDS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000, "million": 1000000})
_NUMBER_PATTERN = r"(?:\d+|" + "|".join(_NUMBER_WORDS) + r")"
_MODEL_VERSION = "local-tfidf-knn-v1"


def _features(text: str) -> Counter:
    tokens = [x for x in re.findall(r"[a-z0-9]+|[\u0600-\u06ff]+", text.lower()) if x not in _STOPWORDS]
    return Counter(tokens + [a + " " + b for a, b in zip(tokens, tokens[1:])])


def _normalise(vector: dict[str, float]) -> dict[str, float]:
    length = sqrt(sum(x * x for x in vector.values()))
    return {key: value / length for key, value in vector.items()} if length else {}


class IntentModel:
    """Supervised nearest-neighbor classifier with learned corpus-wide IDF."""

    def __init__(self, examples: list[dict]):
        self.examples = examples
        counts = [_features(example["text"]) for example in examples]
        frequency = Counter(term for row in counts for term in row)
        self.idf = {term: log((1 + len(counts)) / (1 + count)) + 1 for term, count in frequency.items()}
        self.vectors = [self.vector(row) for row in counts]

    def vector(self, counts: Counter) -> dict[str, float]:
        return _normalise({term: (1 + log(count)) * self.idf[term] for term, count in counts.items() if term in self.idf})

    def classify(self, text: str) -> dict:
        query = self.vector(_features(text))
        matches = sorted(
            ({"intent": example["intent"], "text": example["text"], "similarity": sum(value * vector.get(term, 0) for term, value in query.items())} for example, vector in zip(self.examples, self.vectors)),
            key=lambda row: row["similarity"], reverse=True,
        )
        by_intent = defaultdict(list)
        for row in matches:
            by_intent[row["intent"]].append(row["similarity"])
        scores = {intent: sum(values[:3]) / 3 for intent, values in by_intent.items()}
        ranked = sorted(scores.items(), key=lambda row: row[1], reverse=True)
        winner, score = ranked[0]
        margin = score - ranked[1][1]
        accepted = winner != "unsupported" and score >= 0.12 and margin >= 0.035
        return {"intent": winner if accepted else "unsupported", "similarity": round(score, 4), "margin": round(margin, 4), "matches": [{**row, "similarity": round(row["similarity"], 4)} for row in matches[:3]], "accepted": accepted}


@lru_cache(maxsize=1)
def _intent_model() -> IntentModel:
    path = Path(__file__).resolve().parent.parent / "data" / "intent_corpus.json"
    corpus = json.loads(path.read_text(encoding="utf-8"))
    return IntentModel(corpus["examples"])


def _number(value: str) -> int:
    return _NUMBER_WORDS[value.lower()] if value.lower() in _NUMBER_WORDS else int(value)


def _number_phrases(text: str) -> str:
    words = "|".join(_NUMBER_WORDS)
    def convert(match):
        subtotal, total = 0, 0
        for word in re.split(r"[-\s]+", match.group(0).lower()):
            value = _NUMBER_WORDS[word]
            if value == 100:
                subtotal = max(1, subtotal) * value
            elif value >= 1000:
                total += max(1, subtotal) * value
                subtotal = 0
            else:
                subtotal += value
        return str(total + subtotal)
    return re.sub(r"\b(?:" + words + r")(?:[-\s]+(?:" + words + r"))*\b", convert, text, flags=re.I)


def _quantity(intent: str, text: str) -> tuple[int, str]:
    text = _number_phrases(text)
    if re.search(r"(?:^|\s)-\d+\s+(?:(?:battery|new|protected|18650|water|leaking|tool)\s+){0,4}(?:cells?|batteries|packs?|pumps?|sets?|kits?)\b", text, re.I):
        raise ValueError("Negative requested quantities are invalid.")
    if intent == "battery":
        packs = re.search(r"\b(" + _NUMBER_PATTERN + r")\s+(?:(?:new|reclaimed|tested|battery|cell)\s+){0,3}(?:packs?|4-packs?)\b", text, re.I)
        if packs:
            value = _number(packs.group(1))
            return value, f"Requested {value} four-cell pack(s)."
        units = re.search(r"\b(" + _NUMBER_PATTERN + r")\s+(?:(?:new|reclaimed|tested|protected|18650|lithium|battery)\s+){0,4}(?:cells?|batteries)\b", text, re.I)
        if units and units.group(1) != "18650":
            count = _number(units.group(1))
            value = ceil(count / 4)
            return value, f"Requested {count} cells; {value} four-cell pack(s) supply {value * 4} cells."
        return 1, "No cell count stated; one four-cell pack is the disclosed demo default."
    nouns = r"pumps?|kits?|seals?" if intent == "pump" else r"(?:tool\s+sets?|sets?|kits?)"
    count = re.search(r"\b(" + _NUMBER_PATTERN + r")\s+(?:(?:leaking|broken|damaged|demo|water|seal|repair|insulated|appliance)\s+){0,5}(?:" + nouns + r")\b", text, re.I)
    value = _number(count.group(1)) if count else 1
    return value, f"Requested {value} item(s)." if count else "No count stated; one item is the disclosed demo default."


def _is_constraint_clause(text: str) -> bool:
    return bool(re.fullmatch(
        r"(?:only\s+(?:brand\s+)?new|brand\s+new|repair[ -]first|prefer\s+repair|reuse\s+first|(?:use\s+)?(?:only\s+)?approved\s+suppliers?|avoid\s+(?:waste|landfill))(?:\s+please)?"
        r"|(?:(?:my|our|the)\s+)?(?:budget(?:\s+cap)?(?:\s+(?:is|of|at))?|under|max(?:imum)?(?:\s+(?:spend|cost|budget))?|cap(?:\s+at)?)\s*(?:\$|USD\s*)?\d+(?:\.\d{1,2})?(?:\s+(?:dollars|USD))?"
        r"|(?:use\s+)?only\s+(?:from\s+)?(?:greenloop|recell|fixfirst)(?:\s+demo)?(?:\s+(?:supply|cooperative|parts))?",
        text, re.I))


def _effective_budget(req: PlanRequest) -> float:
    mentioned = re.findall(r"\b(?:budget(?:\s+cap)?(?:\s+(?:is|of|at))?|under|max(?:imum)?(?:\s+(?:spend|cost|budget))?|cap(?:\s+at)?)\s*(?:\$|USD\s*)?(\d+(?:\.\d{1,2})?)(?![.\d])", req.request, re.I)
    budgets = [float(value) for value in mentioned]
    if any(value <= 0 for value in budgets):
        raise ValueError("A budget stated in the request must be greater than zero.")
    return min([float(req.max_budget)] + budgets)


def _effective_suppliers(req: PlanRequest) -> list[str]:
    match = re.search(r"\bonly\s+(?:from\s+)?(greenloop|recell|fixfirst)\b", req.request, re.I)
    if not match:
        return req.allowed_suppliers
    selected = match.group(1).lower() + "-demo"
    return [selected] if selected in req.allowed_suppliers else []


def _requirements(req: PlanRequest) -> tuple[list[dict], set[str], list[dict]]:
    text = req.request.lower()
    excluded = set()
    clauses = [part.strip() for part in re.split(r"[;,]|\b(?:and|but|then)\b|(?<!\d)[.!?](?!\d)", req.request, flags=re.I) if part.strip()]
    for clause in clauses:
        clause = clause.lower()
        negative = r"(?:(?:no|not|avoid|without)\s+|(?:do\s+not|don't|never)\s+(?:buy|use|choose|want)\s+(?:any\s+)?)"
        negative_new = bool(re.search(negative + r"new\s+(?:cells|batteries|packs)", clause))
        negative_reclaimed = bool(re.search(negative + r"(?:reclaimed|used)", clause))
        positive_new = bool(re.search(r"(?:only\s+(?:brand\s+)?new|brand\s+new|new\s+(?:(?:protected|18650|battery|four-cell)\s+){0,3}(?:cells|batteries|packs))", clause))
        positive_reclaimed = bool(re.search(r"(?:only\s+(?:tested\s+)?(?:reclaimed|used)|(?:reclaimed|used)\s+(?:18650\s+)?(?:cells|batteries|packs))", clause))
        if negative_reclaimed or (positive_new and not negative_new):
            excluded.add("BAT-RECLAIM-4")
        if negative_new or (positive_reclaimed and not negative_reclaimed):
            excluded.add("BAT-18650-4")
    if re.search(r"(?:no\s+(?:full\s+)?replacement|(?:do\s+not|don't|never)\s+(?:buy\s+(?:a\s+)?)?replace|without\s+(?:a\s+)?replacement)", text):
        excluded.add("PUMP-REPLACE")
    if re.search(r"(?:beyond\s+repair|cannot\s+(?:be\s+)?repair|can't\s+(?:be\s+)?repair|must\s+replace|only\s+(?:a\s+)?replacement|no\s+(?:seal\s+)?repair\s+kit|(?:do\s+not|don't|never)\s+(?:buy|use|choose|want)\s+(?:(?:a|the|any)\s+)?(?:seal\s+)?repair\s+kit)", text):
        excluded.add("PUMP-SEAL-KIT")
    # An explicit whole-pump replacement outranks the repair-first preference.
    # Replacing a pump seal/gasket still requests the repair kit, not an assembly.
    for clause in clauses:
        explicitly_replace = re.search(r"\breplace\s+(?:(?:the|a|my|our|this|leaking|broken|failed|demo|water)\s+)*pump\b(?!\s+(?:seal|gasket|o-ring|shaft))|\bpump\s+(?:needs?|requires?)\s+(?:a\s+)?replacement\b", clause, re.I)
        negated_replace = re.search(r"(?:do\s+not|don't|never)\s+(?:(?:buy|use|choose|want)\s+)?replace\b", clause, re.I)
        if explicitly_replace and not negated_replace:
            excluded.add("PUMP-SEAL-KIT")
    for pattern, skus in [
        (r"(?:no\s+(?:battery|batteries|cells)|(?:do\s+not|don't)\s+(?:buy|need|want)\s+(?:any\s+)?(?:battery|batteries|cells))", ["BAT-RECLAIM-4", "BAT-18650-4"]),
        (r"(?:(?:no|not)\s+tools|without\s+tools|(?:do\s+not|don't)\s+(?:buy|need|want)\s+(?:any\s+)?tools)", ["TOOL-MULTI"]),
    ]:
        if re.search(pattern, text):
            excluded.update(skus)
    needs = {}
    trace = []
    for clause in clauses:
        if _is_constraint_clause(clause) or re.fullmatch(r"(?:try|prefer|attempt)\s+(?:a\s+)?repair(?:\s+first)?|(?:fix|repair|replace)\s+it\s+(?:under|within)\s+\$?\d+(?:\.\d{1,2})?", clause, re.I):
            trace.append({"step": "request_constraint", "input": clause})
            continue
        inference = _intent_model().classify(clause)
        trace.append({"step": "intent_inference", "input": clause, **inference})
        negative = bool(re.search(r"^\s*(?:(?:i|we|please)\s+)?(?:no\b|not\b|without\b|do\s+not\b|don't\b|never\b|exclude\b|skip\b|avoid\b)", clause, re.I))
        if negative:
            continue
        if inference["intent"] == "unsupported":
            raise ValueError("The local AI could not confidently map every requested item to this demo catalog. Try a leaking water pump, 18650 cells, or insulated appliance repair tools; unsupported requests need clarification.")
        intent = inference["intent"]
        quantity, note = _quantity(intent, clause)
        if not 1 <= quantity <= 5:
            raise ValueError("Requested quantity is outside the demo limit of one to five catalog packs/items per category.")
        if intent in needs:
            # Repeated descriptions do not authorize another purchase; conflicting counts require clarification.
            if needs[intent]["quantity"] != quantity and re.search(_NUMBER_PATTERN, clause, re.I):
                raise ValueError("Conflicting quantities for the same item category need clarification.")
            continue
        needs[intent] = {"intent": intent, "quantity": quantity, "quantity_note": note, "input": clause}
    if not needs:
        raise ValueError("No positive supported purchase request remains after exclusions.")
    return list(needs.values()), excluded, trace


def _candidate(item: dict, need: dict, req: PlanRequest, excluded: set[str]) -> dict:
    findings = []
    if item["sku"] in excluded:
        findings.append("Excluded by the request.")
    if not item["approved"] or item["supplier_id"] not in _effective_suppliers(req):
        findings.append("Supplier is outside the allowed supplier policy.")
    if item["stock"] < need["quantity"]:
        findings.append("Insufficient synthetic inventory.")
    amount = round(item["unit_price"] * need["quantity"], 2)
    return {"sku": item["sku"], "name": item["name"], "intent": need["intent"], "condition": item["condition"], "quantity": need["quantity"], "line_total": amount, "repair_priority": item["repair_priority"], "eligible": not findings, "findings": findings, "evidence_ids": item["evidence_ids"], "selected": False, "synthetic": True}


def _local_plan(req: PlanRequest) -> AgentPlan:
    needs, excluded, trace = _requirements(req)
    candidates = [_candidate(item, need, req, excluded) for need in needs for item in CATALOG if item.get("intent") == need["intent"]]
    choices = [[row for row in candidates if row["intent"] == need["intent"] and row["eligible"]] for need in needs]
    missing = [need["intent"] for need, rows in zip(needs, choices) if not rows]
    findings = [f"No eligible candidate satisfies the request and supplier/stock constraints for {intent}." for intent in missing]
    selected = []
    if not missing:
        combinations = list(product(*choices))
        affordable = [cart for cart in combinations if round(sum(row["line_total"] for row in cart), 2) <= _effective_budget(req)]
        def objective(cart):
            return (sum(row["repair_priority"] for row in cart) if req.repair_first else 0, round(sum(row["line_total"] for row in cart), 2), tuple(row["sku"] for row in cart))
        selected = list(min(affordable or combinations, key=objective))
    selected_skus = {row["sku"] for row in selected}
    for row in candidates:
        row["selected"] = row["sku"] in selected_skus
        if row["eligible"] and not row["selected"]:
            row["findings"].append("Alternative considered; it is not included in this purchase.")
    trace.append({"step": "cart_optimization", "objective": "Minimize repair/reuse priority, then total cost, subject to all requested categories, supplier policy, stock, exclusions, and budget.", "selected_skus": sorted(selected_skus), "candidate_count": len(candidates), "budget_cap": _effective_budget(req), "all_requirements_satisfied": not missing})
    selected_names = ", ".join(row["name"] for row in selected) or "no feasible cart"
    return AgentPlan(
        summary=f"Evidence-bound repair and reuse plan: {selected_names}.",
        items=[RequestedItem(row["sku"], row["quantity"]) for row in selected],
        reasoning="The local trained intent model classified the request. The constraint solver compared catalog alternatives and selected one solution for each requested category. " + " ".join(need["quantity_note"] for need in needs) + " Prices, availability, compatibility, and vendor evidence are synthetic demo data; confirm suitability before checkout.",
        candidates=candidates, decision_trace=trace, policy_findings=findings,
        requirements=needs, exclusions=sorted(excluded), engine=_MODEL_VERSION,
    )


def _model_plan(req: PlanRequest) -> AgentPlan:
    base = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
    key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "")
    if not (base and key and model):
        return _local_plan(req)
    needs, excluded, trace = _requirements(req)
    prompt = {
        "task": "Propose an evidence-bound procurement plan. Output JSON only with summary, items[{sku,quantity}], reasoning.",
        "request": req.request, "requirements": needs, "excluded_skus": sorted(excluded),
        "budget": _effective_budget(req), "allowed_supplier_ids": _effective_suppliers(req),
        "catalog": CATALOG,
        "instruction": "Select exactly one alternative per requested category, exact quantities and exact listed SKUs. Prefer repair/reuse. All catalog data is synthetic; never claim real compatibility, availability, users, savings, or payment. Do not decide payment or approval.",
    }
    request = Request(base + "/chat/completions", data=json.dumps({"model": model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": json.dumps(prompt)}]}).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=20) as response:
        raw = json.loads(response.read(1_000_001))
        data = raw["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(data)
        lines = []
        for row in parsed["items"]:
            if type(row["quantity"]) is not int or not 1 <= row["quantity"] <= 5 or not isinstance(row["sku"], str):
                raise ValueError("Invalid structured item bounds")
            lines.append(RequestedItem(row["sku"], row["quantity"]))
        if not 1 <= len(lines) <= 3 or not isinstance(parsed["summary"], str) or not isinstance(parsed["reasoning"], str):
            raise ValueError("Invalid structured plan")
        candidates = [_candidate(item, need, req, excluded) for need in needs for item in CATALOG if item.get("intent") == need["intent"]]
        selected = {line.sku for line in lines}
        for row in candidates:
            row["selected"] = row["sku"] in selected
        return AgentPlan(parsed["summary"][:700], lines, parsed["reasoning"][:1500], candidates=candidates, decision_trace=trace, requirements=needs, exclusions=sorted(excluded))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("The external AI returned an invalid plan; checkout was blocked.") from exc


def create_plan_sync(req: PlanRequest) -> dict:
    plan = _model_plan(req)
    policy = list(getattr(plan, "policy_findings", []))
    rows = []
    total = 0.0
    requirements = {row["intent"]: row for row in getattr(plan, "requirements", [])}
    exclusions = set(getattr(plan, "exclusions", []))
    seen_intents = set()
    seen_skus = set()
    for line in plan.items:
        item = approved_by_sku(line.sku)
        if item is None:
            policy.append(f"Blocked unknown SKU: {line.sku}.")
            continue
        if type(line.quantity) is not int or not 1 <= line.quantity <= 5:
            policy.append(f"Blocked invalid quantity for {line.sku}.")
            continue
        if line.sku in seen_skus or item.get("intent") in seen_intents:
            policy.append(f"Blocked simultaneous alternatives or duplicate SKU for {line.sku}.")
            continue
        seen_skus.add(line.sku)
        seen_intents.add(item.get("intent"))
        if line.sku in exclusions:
            policy.append(f"Blocked request-excluded SKU: {line.sku}.")
            continue
        if item["supplier_id"] not in _effective_suppliers(req) or not item["approved"]:
            policy.append(f"Blocked unapproved supplier for {line.sku}.")
            continue
        if item["stock"] < line.quantity:
            policy.append(f"Insufficient demo stock for {line.sku}.")
            continue
        if requirements and (item.get("intent") not in requirements or requirements[item["intent"]]["quantity"] != line.quantity):
            policy.append(f"Blocked model item that does not satisfy requested category/quantity: {line.sku}.")
            continue
        line_total = round(item["unit_price"] * line.quantity, 2)
        total += line_total
        rows.append({**item, "quantity": line.quantity, "line_total": line_total})
    total = round(total, 2)
    budget_cap = _effective_budget(req)
    if total > budget_cap:
        policy.append(f"Total ${total:.2f} exceeds the authorized budget cap of ${budget_cap:.2f}.")
    if not rows:
        policy.append("No eligible items remain after policy checks.")
    if requirements and set(requirements) != {row.get("intent") for row in rows}:
        policy.append("The cart does not satisfy every requested category; partial checkout is blocked.")
    if req.currency != "USD":
        policy.append("This demo checkout only supports USD in PayPal sandbox.")
    return {
        "summary": plan.summary, "reasoning": plan.reasoning, "items": rows,
        "subtotal": total, "currency": req.currency, "budget_cap": budget_cap,
        "policy_passed": not policy, "policy_findings": policy, "approval_required": True,
        "candidates": getattr(plan, "candidates", []), "decision_trace": getattr(plan, "decision_trace", []),
        "requirements": getattr(plan, "requirements", []), "exclusions": sorted(exclusions),
        "planner": {"engine": getattr(plan, "engine", "external-structured-model"), "local_model": "Supervised TF-IDF nearest-neighbor classifier", "training_data": "Original synthetic examples in data/intent_corpus.json", "scope": "Demo water-pump repair/replacement, 18650 cells, insulated repair tools", "confidence_notice": "Similarity and margin are retrieval scores, not calibrated probabilities."},
        "catalog_notice": "All supplier, inventory, price, compatibility, and evidence records shown here are synthetic demo fixtures.",
        "catalog_age_note": "This demo does not claim live catalog integrations or verified market offers.",
    }
