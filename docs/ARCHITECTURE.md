# Architecture

DeliverableQA is a single Intelligent Contract with three actors and one consensus boundary.

| Actor | Role |
|---|---|
| **Buyer** | Calls `open_escrow`: locks GEN, an immutable rubric, a spec URL, an optional demo/brand URL, a pass threshold, the **pinned seller address**, and a review window (days). |
| **Seller** | The address pinned at `open_escrow`. Only that address may call `deliver` on the job; submits a public delivery URL and becomes the payee. |
| **Anyone** | Calls `review` on a delivered job. Validators fetch live evidence and judge it. Then `withdraw` for the winning party. |
| **Buyer (recovery)** | If `review` never finalizes before `deadline_date`, calls `reclaim_timeout` to get the escrow back. |

## State machine

```
              open_escrow                deliver                 review (consensus)
 (nothing) ----------------> open ---------------------> delivered ----+----> passed   (seller credited)
                              |                              |         |
                              | cancel (buyer only)          |         +----> failed    (buyer credited)
                              v                              | reclaim_timeout (buyer, past deadline_date)
                          cancelled (buyer credited)          v
                                                           expired (buyer credited)

 withdraw(): pays out credits[caller] at any time, independent of job state.
```

`passed`, `failed`, `cancelled` and `expired` are terminal. A job can be reviewed **once**: `review` requires
`delivered`, and the verdict write moves it out of that state in the same transaction. If consensus fails, the
transaction reverts and the job stays `delivered`, so `review` can be retried -- right up until `deadline_date`.
`reclaim_timeout` requires the *same* `delivered` guard, so whichever of `review` / `reclaim_timeout` lands first
forecloses the other in the same transaction that credits a payee: settlement can never be reclaimed, and a
reclaimed job can never later be "reviewed" into a payout.

## Storage layout

| Field | Type | Notes |
|---|---|---|
| `jobs` | `TreeMap[str, Job]` | keyed by `job_id` (trimmed, 1-64 chars) |
| `credits` | `TreeMap[Address, u256]` | pull-pattern balances |

`Job` is an `@allow_storage @dataclass`: `buyer`, `seller`, `spec_url`, `checks_json`, `demo_url`, `brand_url`,
`delivery_url`, `pass_threshold: u32`, `review_window_days: u32`, `escrow: u256`, `status`, `score: u32`, `passed`,
`result_json`, `deadline_date`. No `list`, `dict` or `int` is ever persisted. `scripts/preflight.py` enforces this.

`checks_json`, `spec_url`, `demo_url`, `brand_url`, `pass_threshold`, `seller` and `review_window_days` are written
once in `open_escrow` and never modified afterward. `deadline_date` is set exactly once, in `deliver`, as
`_add_days(_now(), review_window_days)` -- deterministic civil-calendar arithmetic over the transaction's own
`gl.message_raw["datetime"]`, so leader and validators (and the deterministic zone) always agree on it.

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

* **One judgment, no appeal.** Verdicts are final once accepted.
* **`reclaim_timeout` refunds the buyer, it does not adjudicate.** If the seller *did* deliver something reviewable
  but nobody ever called `review` (or `review` kept hitting a transient fetch failure) before `deadline_date`, the
  buyer can still walk away with a full refund even though the delivery may have been fine. That is the accepted
  trade-off for a bounded lock: `review` remains callable (and preferred) right up until someone calls
  `reclaim_timeout`, so a race to finalize honestly still beats an unearned refund.
