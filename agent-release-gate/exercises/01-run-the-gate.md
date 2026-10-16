# 01 · Run the gate (10 min)

**Goal:** run the golden set, read what the gate measures, and record a baseline.

1. Run the gate against the committed baseline:

   ```bash
   python -m goldengate run --suite golden/listings.jsonl --schema golden/listing.schema.json \
     --agent py:agents.listing_agent:extract
   ```

   You should see `GATE: PASS` and 12/12.

2. Open `.goldengate/report.json`. Find case `c04-no-size`. What did the agent return for `size`,
   and why is that right?

3. Open `.goldengate/metrics.prom`. Which lines would you put on a dashboard for your manager, and
   which for your on-call engineer?

4. Record your own baseline in a scratch file so you don't touch the committed one:

   ```bash
   python -m goldengate run --suite golden/listings.jsonl --schema golden/listing.schema.json \
     --agent py:agents.listing_agent:extract --baseline my-baseline.json --set-baseline
   ```

**Discuss:** the committed baseline lives in the repo. Who should approve a change to it, and why?
