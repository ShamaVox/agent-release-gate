# 04 · Catch the invention (10 min)

**Goal:** see why checking shape is not enough.

The `invent` variant fills a missing colour with a plausible guess. The output is perfectly shaped.

```bash
AGENT_VARIANT=invent python -m goldengate run --suite golden/listings.jsonl \
  --schema golden/listing.schema.json --agent py:agents.listing_agent:extract
```

1. Look at `c06-no-colour` in `.goldengate/report.json`. The shape grader found nothing. Which grader
   caught it, and how?
2. Now try `AGENT_VARIANT=schema-drift`. Which grader fires this time? Would a JSON-schema check in
   your current CI have caught `invent`? Would it have caught `schema-drift`?
3. Open `golden/listing.schema.json` and change `color`'s truth rule to `"none"`. Run `invent`
   again. The gate still blocks, but "invented values" drops to 0. Which grader is still catching it,
   and what happens on live traffic, where nobody wrote down the right answer? Change it back.

**Discuss:** "Old gates check shape. New gates check truth." Where in your own product could an agent
produce a confident, well-formed, invented answer?
