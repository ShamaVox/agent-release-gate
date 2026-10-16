"""The workshop's example agent: turns messy supplier text into a product listing.

It is deterministic on purpose (no API key, no network) so every laptop sees the same results. The
variants stand in for the changes that break real agents:

  baseline      the known-good agent
  model-swap    a "cheaper model" that misreads prices written with thousands separators (1,299.00)
  invent        fills a missing colour with a plausible guess instead of leaving it empty
  schema-drift  returns the price as a string ("148.00") after a prompt edit

Pick one with the AGENT_VARIANT environment variable, or call extract_with() directly.
Run it as a command too:  echo '{"input": "..."}' | python agents/listing_agent.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

VARIANTS = ("baseline", "model-swap", "invent", "schema-drift")

COLOURS = (
    "black", "white", "ivory", "cream", "navy", "blue", "sage", "olive", "green", "emerald",
    "red", "burgundy", "blush", "pink", "camel", "tan", "brown", "grey", "gray", "charcoal",
)
CURRENCY = {"US$": "USD", "$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}

_CODE = r"([A-Z]{0,4}-?\d[A-Z0-9-]*)"
_SKU_PATTERNS = (  # most explicit label first, so "Item: Merino Beanie" is never read as a SKU
    re.compile(r"\bSKU\s*[:#]?\s*" + _CODE, re.IGNORECASE),
    re.compile(r"\bItem\s*(?:no\.?|#)\s*" + _CODE, re.IGNORECASE),
    re.compile(r"\bStyle\s*(?:no\.?|#)\s*" + _CODE, re.IGNORECASE),
)
_PRICE_BEFORE = re.compile(r"(US\$|\$|€|£|USD|EUR|GBP)\s?(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)")
_PRICE_AFTER = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)\s?(USD|EUR|GBP|€)")
_SIZE = re.compile(r"\b(?:size|sz)\s*[:\-]?\s*(XXS|XS|S|M|L|XL|XXL|\d{1,2})\b", re.IGNORECASE)
_SEPARATORS = re.compile(r"\s*(?:\||;|\s-\s|\s/\s|\n)\s*")


def _price(text: str, variant: str) -> tuple[float | None, str | None]:
    m = _PRICE_BEFORE.search(text)
    if m:
        symbol, amount = m.group(1), m.group(2)
    else:
        m = _PRICE_AFTER.search(text)
        if not m:
            return None, None
        amount, symbol = m.group(1), m.group(2)
    if variant == "model-swap" and "," in amount:
        amount = amount.split(",")[0]  # the regression: "1,299.00" read as 1
    return float(amount.replace(",", "")), CURRENCY[symbol.upper() if symbol.isalpha() else symbol]


def _sku(text: str) -> str | None:
    for pattern in _SKU_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1).upper()
    return None


def _colour(text: str) -> str | None:
    for word in re.findall(r"[A-Za-z]+", text):
        if word.lower() in COLOURS:
            return word.capitalize()
    return None


def _title(text: str) -> str:
    first = _SEPARATORS.split(text.strip(), maxsplit=1)[0]
    first = re.sub(r"^(?:item|product|name)\s*:\s*", "", first, flags=re.IGNORECASE)
    return " ".join(w.capitalize() if w.isupper() or w.islower() else w for w in first.split())


def extract_with(text: str, variant: str = "baseline") -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; choose one of {', '.join(VARIANTS)}")
    price, currency = _price(text, variant)
    size = _SIZE.search(text)
    colour = _colour(text)
    if colour is None and variant == "invent":
        colour = "Black"  # the regression: a confident guess the source never made
    listing: dict[str, Any] = {
        "title": _title(text),
        "price": price,
        "currency": currency,
        "size": size.group(1).upper() if size else None,
        "color": colour,
        "sku": _sku(text),
    }
    if variant == "schema-drift" and price is not None:
        listing["price"] = f"{price:.2f}"
    return listing


def extract(text: str) -> dict[str, Any]:
    return extract_with(text, os.environ.get("AGENT_VARIANT", "baseline"))


if __name__ == "__main__":
    request = json.load(sys.stdin)
    json.dump(extract(request["input"]), sys.stdout)
