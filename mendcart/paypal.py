"""PayPal Orders v2 client restricted to the exact sandbox API origin."""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .config import public_origin

SANDBOX_API = "https://api-m.sandbox.paypal.com"
_token_lock = threading.RLock()
_token_cache: dict = {}


class PayPalError(RuntimeError):
    """Sanitized provider error; secrets and provider bodies are never exposed."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PayPalError("PayPal sandbox redirected unexpectedly; request stopped.")


_open = build_opener(_NoRedirect()).open


def _base_url() -> str:
    base = os.getenv("PAYPAL_BASE_URL", SANDBOX_API).rstrip("/")
    if base != SANDBOX_API:
        raise ValueError("PayPal API origin must be exactly https://api-m.sandbox.paypal.com.")
    return base


def sandbox_ready() -> bool:
    _base_url()
    return bool(os.getenv("PAYPAL_CLIENT_ID", "").strip() and os.getenv("PAYPAL_CLIENT_SECRET", "").strip())


def _request(request: Request) -> dict:
    try:
        with _open(request, timeout=25) as response:
            result = json.loads(response.read(1_000_001))
            if not isinstance(result, dict):
                raise PayPalError("PayPal sandbox returned an invalid response.")
            return result
    except HTTPError as exc:
        raise PayPalError(f"PayPal sandbox returned HTTP {exc.code}; check sandbox credentials and order state.") from None
    except (URLError, TimeoutError, OSError):
        raise PayPalError("PayPal sandbox is unreachable. Retry the same plan or order; its request ID is stable.") from None
    except (ValueError, UnicodeError):
        raise PayPalError("PayPal sandbox returned an unreadable response.") from None


def _access_token() -> str:
    if not sandbox_ready():
        raise PayPalError("PayPal sandbox credentials are not configured.")
    credentials = (os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"])
    with _token_lock:
        if _token_cache.get("credentials") == credentials and _token_cache.get("until", 0) > time.monotonic():
            return _token_cache["token"]
        basic = base64.b64encode(f"{credentials[0]}:{credentials[1]}".encode()).decode()
        result = _request(Request(_base_url() + "/v1/oauth2/token", data=b"grant_type=client_credentials",
                                  headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"}, method="POST"))
        token = result.get("access_token")
        if not isinstance(token, str) or not token:
            raise PayPalError("PayPal sandbox did not issue an access token.")
        try:
            lifetime = max(0, min(float(result.get("expires_in", 0)) - 60, 28_800))
        except (ValueError, TypeError):
            lifetime = 0
        _token_cache.update(credentials=credentials, token=token, until=time.monotonic() + lifetime)
        return token


def _call(method: str, path: str, data: dict | None = None, request_id: str | None = None) -> dict:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {_access_token()}", "Prefer": "return=representation"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    request = Request(_base_url() + path, data=None if method == "GET" else json.dumps(data or {}).encode(),
                      headers=headers, method=method)
    return _request(request)


def money(value) -> Decimal:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Invalid USD amount.")
        return amount
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid USD amount.") from None


def order_payload(plan: dict, plan_id: str, origin: str | None = None) -> dict:
    if not plan.get("policy_passed") or not plan.get("approval_required") or plan.get("currency") != "USD":
        raise ValueError("The server plan did not pass USD checkout policy.")
    items = []
    total = Decimal("0")
    for row in plan.get("items", []):
        quantity = row.get("quantity")
        if type(quantity) is not int or not 1 <= quantity <= 5:
            raise ValueError("Invalid checkout quantity.")
        unit = money(row["unit_price"])
        total += unit * quantity
        items.append({"name": row["name"][:127], "sku": row["sku"][:127], "quantity": str(quantity),
                      "unit_amount": {"currency_code": "USD", "value": f"{unit:.2f}"}, "category": "PHYSICAL_GOODS"})
    if not items or total != money(plan["subtotal"]) or not 0 < total <= money(plan["budget_cap"]):
        raise ValueError("Checkout amount does not match the approved server plan.")
    origin = public_origin() if origin is None else origin
    return {"intent": "CAPTURE", "purchase_units": [{
        "reference_id": plan_id, "custom_id": plan_id,
        "description": "MendCart approved synthetic procurement demo",
        "amount": {"currency_code": "USD", "value": f"{total:.2f}",
                   "breakdown": {"item_total": {"currency_code": "USD", "value": f"{total:.2f}"}}},
        "items": items}],
        "payment_source": {"paypal": {"experience_context": {
            "brand_name": "MendCart Sandbox", "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING",
            "return_url": origin + "/?paypal=return", "cancel_url": origin + "/?paypal=cancel"}}}}


def create_order(plan: dict, plan_id: str, request_id: str, origin: str | None = None) -> dict:
    return _call("POST", "/v2/checkout/orders", order_payload(plan, plan_id, origin), request_id)


def _valid_order_id(order_id: str) -> str:
    if not isinstance(order_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", order_id):
        raise ValueError("Invalid sandbox order ID.")
    return order_id


def get_order(order_id: str) -> dict:
    return _call("GET", "/v2/checkout/orders/" + _valid_order_id(order_id))


def capture_order(order_id: str, request_id: str) -> dict:
    return _call("POST", "/v2/checkout/orders/" + _valid_order_id(order_id) + "/capture", {}, request_id)


def approval_url(order: dict) -> str | None:
    for link in order.get("links", []):
        if link.get("rel") not in {"approve", "payer-action"}:
            continue
        href = link.get("href", "")
        parsed = urlsplit(href)
        if (parsed.scheme != "https" or parsed.hostname not in {"www.sandbox.paypal.com", "sandbox.paypal.com"}
                or parsed.username or parsed.password or parsed.port not in {None, 443}):
            raise PayPalError("PayPal returned an unexpected payer approval origin.")
        return href
    return None
