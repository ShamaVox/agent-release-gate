# Agent Release Gate

**Build a golden set, gate every change, and catch the answers your agent invents.**

Starter code for the workshop *Build Your Golden Set: A Hands-On Release Gate for AI Agents* by
[Shama Keskar](#about-the-author).

AI agents rarely fail with a crash. They fail with a confident, well-formatted answer that is wrong.
A traditional test suite waves that through: green build, wrong answer. This repo is a small,
complete release gate that checks **truth**, not just shape, on every change, and blocks the change
when quality drops.

![Architecture of the agent release gate](docs/architecture.svg)

- **No API key, no installs.** Python 3.10+ and the standard library. The example agent is
  deterministic, so every laptop in the room sees the same results.
- **Bring your own agent.** Any Python function or any program that reads JSON and writes JSON.
- **CI-ready.** Exit code 0 passes, 1 blocks, 2 is a configuration error. A GitHub Actions workflow
  is included.
- **Measured.** Every run writes `report.json` and Prometheus-format `metrics.prom`.

## Quickstart (2 minutes)

```bash
git clone https://github.com/shamavox/agent-release-gate.git
cd agent-release-gate

# Run the golden set and gate against the committed baseline
python -m goldengate run \
  --suite golden/listings.jsonl \
  --schema golden/listing.schema.json \
  --agent py:agents.listing_agent:extract
```

```
goldengate · suite listings (12 cases) · agent py:agents.listing_agent:extract
  first-pass success  12/12  100.0%   (baseline 100.0%)
  field accuracy      100.0%
  invented values     0
  agent errors        0
  latency p50 / p95   0.1 / 0.7 ms
GATE: PASS
```

Now "swap the model" to a cheaper one and run it again:

```bash
AGENT_VARIANT=model-swap python -m goldengate run \
  --suite golden/listings.jsonl --schema golden/listing.schema.json \
  --agent py:agents.listing_agent:extract
```

```
GATE: BLOCKED
  - 4 case(s) that passed in the baseline now fail: c02-thousands, c04-no-size, c09-colour-last, c10-eur-thousands
  - first-pass success fell from 100.0% to 66.7% (allowed drop 0.0%)
  - 4 invented value(s) not found in the source (allowed 0)
      c02-thousands price: 1.0 is not a number in the source
      c02-thousands price: expected 1299.0, got 1.0
      ...
```

On Windows PowerShell, set the variant with `$env:AGENT_VARIANT="model-swap"` before the command.

## How it works

| Piece | File | What it does |
|---|---|---|
| Golden set | `golden/listings.jsonl` | Real inputs with known-right answers, one JSON case per line |
| Schema | `golden/listing.schema.json` | Fields, types, and how each value is traced to the source |
| Runner | `goldengate/runner.py` | Calls the agent per case, times it, isolates errors and timeouts |
| Graders | `goldengate/graders.py` | **Shape** (structure), **truth** (every value is in the source), **correctness** (matches the answer) |
| Gate | `goldengate/baseline.py` | Compares with the committed baseline and decides |
| Seeding | `goldengate/seeding.py` | Breaks known-good outputs on purpose to prove the graders catch every break |
| Metrics | `goldengate/metrics.py` | Quality and operational metrics in Prometheus text format |

### How the gate decides

![Decision flow of the gate](docs/gate-decision.svg)

The defaults are strict on purpose. Loosen them in a reviewed change, never quietly:

| Flag | Default | Meaning |
|---|---|---|
| `--max-rate-drop` | `0` | Allowed fall in first-pass success (0.02 = 2 points) |
| `--max-invented` | `0` | Values not traceable to the source that a run may contain |
| `--allow-removed-cases` | off | Deleting a golden case is how a gate quietly gets weaker |
| `--timeout` | `30` | Seconds per case before it counts as failed |

### Truth rules

Each schema field says how its value is traced back to the input:

| Rule | Passes when |
|---|---|
| `"verbatim"` | the value appears in the source (case and whitespace insensitive) |
| `"number"` | a number in the source equals the value (`1,299.00` reads as 1299) |
| `{"evidence": {"USD": ["$", "USD"]}}` | the value is allowed and one of its tokens is in the source |
| `"none"` | not checked; use sparingly, an unchecked field can be invented unnoticed |

## The workshop

60 minutes, laptops with Python 3.10+. No accounts, keys or installs.

| Time | Exercise | You will |
|---|---|---|
| 0–5 | Why | See a green build ship a wrong answer |
| 5–15 | [01 · Run the gate](exercises/01-run-the-gate.md) | Run the golden set, read the report, set a baseline |
| 15–25 | [02 · Write golden cases](exercises/02-write-golden-cases.md) | Add three cases from real supplier lines |
| 25–35 | [03 · Swap the model](exercises/03-swap-the-model.md) | Watch the gate block a "cheaper model" and name the cases |
| 35–45 | [04 · Catch the invention](exercises/04-catch-the-invention.md) | See shape pass and truth fail on a confident guess |
| 45–55 | [05 · Seed and ship](exercises/05-seed-and-ship.md) | Prove the gate catches every seeded regression, wire it into CI |
| 55–60 | Three habits | Golden set this week, five metrics daily, "resolved" means proven |

## Bring your own agent

**A Python function** that takes the input text and returns a dict:

```bash
python -m goldengate run --suite my.jsonl --schema my.schema.json --agent py:my_package.my_agent:run
```

**Any program**, in any language. The gate writes `{"input": "..."}` to its stdin and reads the output
object as JSON from its stdout. Exit code 0 means success.

```bash
python -m goldengate run --suite my.jsonl --schema my.schema.json --agent "cmd:node my-agent.js"
```

If your agent calls a model API, keep the golden set small (20 to 50 cases), set `--timeout`, and
run the gate in CI on every pull request that changes a prompt, a model, a tool or the agent code.

## Metrics

Each run writes `.goldengate/metrics.prom` (point a node_exporter textfile collector at it, or keep
it as a CI artifact) and `.goldengate/report.json` with every case's output and findings.

| Metric | Kind |
|---|---|
| `goldengate_first_pass_success_ratio` | quality: share of cases passed with no findings |
| `goldengate_field_accuracy_ratio` | quality: share of fields equal to the known-right answer |
| `goldengate_invented_values` | quality: values not traceable to the source |
| `goldengate_regressed_cases` | quality: cases that passed in the baseline and fail now |
| `goldengate_cases`, `goldengate_cases_passed`, `goldengate_case_errors` | operational |
| `goldengate_agent_latency_ms{quantile="0.5"\|"0.95"}` | operational |
| `goldengate_run_duration_seconds`, `goldengate_gate_blocked` | operational |

## Run the tests

```bash
python -m unittest discover -s tests -t .
```

Unit tests cover the schema, graders, golden-set loading, runner, gate policy, metrics, agents and
seeding. Integration tests drive the real command line end to end. Regression tests pin the example
agent's outputs and exactly which cases each broken variant fails.

## Project layout

```
agents/listing_agent.py     example agent with four variants (baseline, model-swap, invent, schema-drift)
golden/                     golden set and schema
baselines/listings.json     committed baseline (re-baseline only in a reviewed change)
goldengate/                 the gate (standard library only)
exercises/                  workshop exercises
docs/                       architecture and decision diagrams
tests/                      unit, integration and regression tests
.github/workflows/gate.yml  CI: tests on Python 3.10 to 3.13, then the gate
```

## About the author

**Shama Keskar** is a three-time startup CTO. She started as a test engineer at Google and spent
16 years at Google, LinkedIn and Amazon. She takes agentic AI from demo to production.

- LinkedIn: https://www.linkedin.com/in/shamakeskar/
- Plumbline, the full version of these ideas: https://shamavox.github.io/plumbline

## License

MIT. See [LICENSE](LICENSE).
