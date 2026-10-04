"""Session-owned immutable plans and sandbox order state for one demo process."""

from __future__ import annotations

import copy
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def timestamp(value: float | None = None) -> str:
    return datetime.fromtimestamp(value if value is not None else time.time(), timezone.utc).isoformat()


@dataclass
class PlanRecord:
    plan_id: str
    owner: str
    plan: dict
    request: dict
    expires: float
    approved_at: str | None = None
    create_request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    capture_request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order: dict | None = None
    capture: dict | None = None
    events: list[dict] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def event(self, action: str, **details) -> None:
        self.events.append({"at": timestamp(), "action": action, **details})

    def snapshot(self) -> dict:
        with self.lock:
            return {**copy.deepcopy(self.plan), "plan_id": self.plan_id,
                    "expires_at": timestamp(self.expires),
                    "approval_recorded": bool(self.approved_at),
                    "approved_at": self.approved_at, "events": copy.deepcopy(self.events)}


class DemoStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.sessions: set[str] = set()
        self.plans: dict[str, PlanRecord] = {}
        self.orders: dict[str, str] = {}

    def session(self, proposed: str | None) -> tuple[str, bool]:
        with self.lock:
            if proposed in self.sessions:
                return proposed, False
            if len(self.sessions) >= 2048:
                raise ValueError("Demo session limit reached. Restart the local demo.")
            token = secrets.token_hex(32)
            self.sessions.add(token)
            return token, True

    def put(self, owner: str, plan: dict, request: dict) -> PlanRecord:
        with self.lock:
            if len(self.plans) >= 1024:
                raise ValueError("Demo plan limit reached. Restart the local demo.")
            record = PlanRecord(secrets.token_hex(16), owner, copy.deepcopy(plan),
                                copy.deepcopy(request), time.time() + 30 * 60)
            record.event("plan_created", policy_passed=bool(plan.get("policy_passed")),
                         amount=plan.get("subtotal"), currency=plan.get("currency"))
            self.plans[record.plan_id] = record
            return record

    def plan(self, owner: str, plan_id: str, fresh: bool = False) -> PlanRecord:
        with self.lock:
            record = self.plans.get(plan_id)
            if record is None or record.owner != owner:
                raise PermissionError("Plan is unavailable in this browser session.")
            if fresh and time.time() >= record.expires:
                raise ValueError("Plan expired. Generate and approve a new plan.")
            return record

    def bind_order(self, record: PlanRecord, order: dict) -> None:
        with self.lock:
            order_id = order.get("id")
            if not isinstance(order_id, str) or not order_id:
                raise ValueError("PayPal did not return a sandbox order ID.")
            previous = self.orders.get(order_id)
            if previous is not None and previous != record.plan_id:
                raise ValueError("Sandbox order is already bound to another plan.")
            record.order = copy.deepcopy(order)
            self.orders[order_id] = record.plan_id
            record.event("sandbox_order_created", order_id=order_id, status=order.get("status"))

    def order(self, owner: str, order_id: str) -> PlanRecord:
        with self.lock:
            plan_id = self.orders.get(order_id)
            if plan_id is None:
                raise PermissionError("Order is unavailable in this browser session.")
            return self.plan(owner, plan_id)
