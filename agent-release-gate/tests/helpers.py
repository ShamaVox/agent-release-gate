from __future__ import annotations

from pathlib import Path

from goldengate.schema import load_schema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "golden" / "listing.schema.json"
SUITE_PATH = ROOT / "golden" / "listings.jsonl"
SCHEMA = load_schema(SCHEMA_PATH)

SOURCE = "LINEN WRAP DRESS | col: Sage | sz M | $1,148.00 | SKU LW-20391"
GOOD = {"title": "Linen Wrap Dress", "price": 1148.0, "currency": "USD", "size": "M", "color": "Sage", "sku": "LW-20391"}
