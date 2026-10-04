"""Synthetic fixtures for the local demo. These are not real vendors or offers."""

from __future__ import annotations

from datetime import datetime, timezone

CATALOG = [
    {
        "sku": "BAT-18650-4",
        "name": "Protected 18650 cell, 4-pack",
        "category": "battery",
        "intent": "battery",
        "pack_size": 4,
        "unit_price": 18.50,
        "supplier": "GreenLoop Demo Supply",
        "supplier_id": "greenloop-demo",
        "approved": True,
        "stock": 28,
        "condition": "new",
        "repair_priority": 1,
        "evidence": "Synthetic fixture: four protected 18650 cells; simulated supplier and inventory record.",
        "evidence_ids": ["SYN-BAT-NEW-SPEC", "SYN-GREENLOOP-STOCK"],
        "synthetic": True,
    },
    {
        "sku": "BAT-RECLAIM-4",
        "name": "Tested reclaimed 18650 cell, 4-pack",
        "category": "battery",
        "intent": "battery",
        "pack_size": 4,
        "unit_price": 11.00,
        "supplier": "ReCell Demo Cooperative",
        "supplier_id": "recell-demo",
        "approved": True,
        "stock": 7,
        "condition": "reclaimed-tested",
        "repair_priority": 0,
        "evidence": "Demo fixture: reclaimed cells individually capacity-tested; synthetic evidence.",
        "evidence_ids": ["SYN-RECLAIM-CAPACITY", "SYN-RECELL-STOCK"],
        "synthetic": True,
    },
    {
        "sku": "PUMP-SEAL-KIT",
        "name": "Demo P100 water-pump seal repair kit",
        "category": "repair-part",
        "intent": "pump",
        "unit_price": 24.00,
        "supplier": "FixFirst Demo Parts",
        "supplier_id": "fixfirst-demo",
        "approved": True,
        "stock": 13,
        "condition": "new",
        "repair_priority": 0,
        "evidence": "Synthetic fixture: compatibility is modeled only for the fictional Demo P100 pump; inspect the real appliance before any real purchase.",
        "evidence_ids": ["SYN-P100-SEAL-COMPATIBILITY", "SYN-FIXFIRST-STOCK"],
        "compatibility": "Fictional Demo P100 only; real compatibility is unverified.",
        "synthetic": True,
    },
    {
        "sku": "PUMP-REPLACE",
        "name": "Replacement water pump assembly",
        "category": "appliance",
        "intent": "pump",
        "unit_price": 94.00,
        "supplier": "FixFirst Demo Parts",
        "supplier_id": "fixfirst-demo",
        "approved": True,
        "stock": 4,
        "condition": "new",
        "repair_priority": 3,
        "evidence": "Synthetic fixture: modeled for the fictional Demo P100 pump; considered when replacement is requested or repair is ineligible.",
        "evidence_ids": ["SYN-P100-ASSEMBLY", "SYN-FIXFIRST-STOCK"],
        "compatibility": "Fictional Demo P100 only; real compatibility is unverified.",
        "synthetic": True,
    },
    {
        "sku": "TOOL-MULTI",
        "name": "Insulated appliance repair tool set",
        "category": "tool",
        "intent": "tools",
        "unit_price": 31.00,
        "supplier": "GreenLoop Demo Supply",
        "supplier_id": "greenloop-demo",
        "approved": True,
        "stock": 19,
        "condition": "new",
        "repair_priority": 1,
        "evidence": "Synthetic fixture: simulated supplier and insulation specification; no real safety certification is asserted.",
        "evidence_ids": ["SYN-TOOLS-SPEC", "SYN-GREENLOOP-STOCK"],
        "synthetic": True,
    },
    {
        "sku": "UNKNOWN-GADGET",
        "name": "Unverified high-capacity gadget bundle",
        "category": "unknown",
        "intent": "unsupported",
        "unit_price": 9.00,
        "supplier": "FlashOutlet Demo",
        "supplier_id": "flashoutlet-demo",
        "approved": False,
        "stock": 999,
        "condition": "unknown",
        "repair_priority": 9,
        "evidence": "Demo fixture: supplier is not in procurement policy.",
        "evidence_ids": ["SYN-UNAPPROVED-SUPPLIER"],
        "synthetic": True,
    },
]

CATALOG_AS_OF = datetime.now(timezone.utc).isoformat()


def public_catalog() -> list[dict]:
    return [dict(item) for item in CATALOG]


def approved_by_sku(sku: str) -> dict | None:
    return next((dict(item) for item in CATALOG if item["sku"] == sku), None)
