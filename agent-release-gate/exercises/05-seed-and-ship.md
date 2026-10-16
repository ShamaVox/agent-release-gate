# 05 · Seed and ship (10 min)

**Goal:** prove the gate catches what it claims to, then make it run on every change.

## Seed regressions

A gate you have never seen fail is a gate you can't trust. Break the known-good outputs on purpose:

```bash
python -m goldengate seed --suite golden/listings.jsonl --schema golden/listing.schema.json \
  --agent py:agents.listing_agent:extract
```

```
seeded regressions caught: 246 / 246
```

For every passing case and every field, `seed` drops the field, changes its type, changes its value,
nulls it, or invents a value the source never had, and checks that the graders fail the case.

1. Add your three cases from exercise 02. How many seeded regressions now?
2. Set the `title` truth rule to `"none"` and seed again. Nothing escapes. Why? (Hint: the golden
   set knows the right title.) Now think about live traffic, where there is no known answer. Which
   grader is the only one left standing there? Change the rule back.

## Ship it

`.github/workflows/gate.yml` runs the tests on Python 3.10 to 3.13 and then the gate against the
committed baseline on every push and pull request. Push this repo to GitHub and open a pull request
that sets `AGENT_VARIANT: model-swap` in the workflow's gate step. The check goes red and names the
cases.

## Three habits to take home

1. **Build a golden set this week.** Fifty real cases with known-right answers. Run every agent
   change against it.
2. **Watch five metrics daily.** Not monthly. Drift lives in the gap.
3. **Make "resolved" mean proven.** No alert closes until the number moves.
