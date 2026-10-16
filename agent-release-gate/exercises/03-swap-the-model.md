# 03 · Swap the model (10 min)

**Goal:** watch the gate block a change that looks like an upgrade.

The `model-swap` variant stands in for a cheaper model that reads most listings perfectly but
misreads prices written with a thousands separator.

```bash
AGENT_VARIANT=model-swap python -m goldengate run --suite golden/listings.jsonl \
  --schema golden/listing.schema.json --agent py:agents.listing_agent:extract
```

(PowerShell: `$env:AGENT_VARIANT="model-swap"`, then the command.)

1. Which cases regressed? What do they have in common?
2. Field accuracy is still above 94%. Why is that number dangerous on its own?
3. The price `1.0` is flagged as *invented*. It isn't anywhere in the source. Is "invented" the right
   word for a misread number? What would your users call it?
4. Try `--max-rate-drop 0.5`. The gate still blocks. Which rule is holding the line now?

**Discuss:** your team wants the cheaper model. What would you need to see before re-baselining?
