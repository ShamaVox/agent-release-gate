"""Rewrite the example agent's output snapshot. Run only after deciding the new behaviour is right."""

import json

from agents.listing_agent import extract_with
from goldengate.cases import load_suite
from tests.helpers import SCHEMA, SUITE_PATH
from tests.regression.test_known_behaviour import SNAPSHOT

if __name__ == "__main__":
    outputs = {c.id: extract_with(c.input) for c in load_suite(SUITE_PATH, SCHEMA)}
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(outputs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {SNAPSHOT} ({len(outputs)} cases)")
