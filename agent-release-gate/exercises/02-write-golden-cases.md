# 02 · Write golden cases (10 min)

**Goal:** turn real inputs into cases with known-right answers. This is the most valuable hour your
team will spend on agent quality.

Add these three supplier lines to `golden/listings.jsonl`, one JSON object per line, with the
listing you know is right:

```
Ribbed Tank Top | Cream | size XS | $28 | SKU RT-301
Pleated Trousers - Grey - Size 12 - 1,050.00 USD - SKU PT-1200
Bucket Hat | £22.50 | SKU BH-9
```

A case looks like this:

```json
{"id": "c13-tank", "input": "Ribbed Tank Top | Cream | size XS | $28 | SKU RT-301", "expected": {"title": "Ribbed Tank Top", "price": 28.0, "currency": "USD", "size": "XS", "color": "Cream", "sku": "RT-301"}, "tags": ["workshop"]}
```

Then run the gate with your scratch baseline:

```bash
python -m goldengate run --suite golden/listings.jsonl --schema golden/listing.schema.json \
  --agent py:agents.listing_agent:extract --baseline my-baseline.json
```

The new cases show under `new:`. They don't block, because the baseline has never seen them. Record
them with `--set-baseline` once you are sure the expected answers are right.

**Rules of thumb for a golden set**

- Real inputs, not invented ones. Pull them from production logs or support tickets.
- Cover the messy edges: missing fields, odd separators, other currencies, thousands separators.
- When a field is missing in the source, the right answer is `null`. Say so explicitly.
- Fifty cases beats five hundred you never review.

**Discuss:** the gate rejects a case whose `expected` doesn't match the schema. Try it with
`"price": "28"`. Why check the answer key too?
