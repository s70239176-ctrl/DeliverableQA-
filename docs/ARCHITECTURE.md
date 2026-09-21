# Architecture

DeliverableQA is a single Intelligent Contract with three actors and one consensus boundary.

| Actor | Role |
|---|---|
| **Buyer** | Calls `open_escrow`: locks GEN, an immutable rubric, a spec URL, an optional demo/brand URL, and a pass threshold. |
| **Seller** | Whoever first calls `deliver` on an open job. Submits a public delivery URL and becomes the payee. |
| **Anyone** | Calls `review` on a delivered job. Validators fetch live evidence and judge it. Then `withdraw` for the winning party. |

## State machine

```
              open_escrow                deliver                 review (consensus)
 (nothing) ----------------> open ---------------------> delivered ----+----> passed  (seller credited)
                              |                                        |
                              | cancel (buyer only)                    +----> failed  (buyer credited)
                              v
                          cancelled (buyer credited)

 withdraw(): pays out credits[caller] at any time, independent of job state.
```

`passed`, `failed` and `cancelled` are terminal. A job can be reviewed **once**: `review` requires `delivered`, and the
verdict write moves it out of that state in the same transaction. If consensus fails, the transaction reverts and the
job stays `delivered`, so `review` can be retried.

## Storage layout

| Field | Type | Notes |
|---|---|---|
| `jobs` | `TreeMap[str, Job]` | keyed by `job_id` (trimmed, 1-64 chars) |
| `credits` | `TreeMap[Address, u256]` | pull-pattern balances |

`Job` is an `@allow_storage @dataclass`: `buyer`, `seller`, `spec_url`, `checks_json`, `demo_url`, `brand_url`,
`delivery_url`, `pass_threshold: u32`, `escrow: u256`, `status`, `score: u32`, `passed`, `result_json`.
No `list`, `dict` or `int` is ever persisted. `scripts/preflight.py` enforces this.

`checks_json`, `spec_url`, `demo_url`, `brand_url` and `pass_threshold` are written once in `open_escrow` and never
modified afterward.

## Value flow (pull payments)

```
open_escrow --value--> job.escrow
review / cancel: job.escrow -> credits[payee]; job.escrow = 0        (deterministic zone, after consensus)
withdraw:        credits[caller] = 0, then emit_transfer(caller)     (checks-effects-interactions)
```

Why credits instead of paying inside `review`:

* value transfers are forbidden inside nondet blocks, so the verdict path must only do accounting;
* a failing recipient can never block a verdict;
* `withdraw` is the only place value leaves the contract.

**Conservation invariant** (asserted in `tests/simulated`, after every step of a mixed flow):

```
total GEN deposited == sum(job.escrow) + sum(credits) + total withdrawn
```

## What is and is not immutable

The *rubric, URLs and threshold* are immutable. The *content behind the URLs* is live by design: `review` fetches
whatever the URLs serve at review time. Consequences:

* a seller could edit a delivery page between `deliver` and `review`, and a buyer could edit the spec page;
* to freeze evidence, use content-addressed URLs (e.g. `raw.githubusercontent.com/<org>/<repo>/<commit-sha>/README.md`).

## Known design limits

* **Seller slot is first-come.** The seller is set by the first `deliver` call. A stranger can deliver junk first; the
  job then fails and the buyer is refunded (nobody loses funds, but the buyer must reopen). A production version would
  pin an intended seller in `open_escrow` (needs one more argument, so it is outside this spec).
* **No timeouts.** A delivered job that nobody reviews stays locked, and an open job stays open until cancelled.
* **One judgment, no appeal.** Verdicts are final once accepted.
