# Consensus design

`review()` has **one** consensus boundary, built with `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`.
`strict_eq` is never used: LLM output is not byte-identical across validators, and the comparison we want is
structured (decision, per-check verdicts, bounded score), not textual.

## Before the boundary (deterministic, has storage access)

`review` copies everything the nondet code needs into plain Python values with `gl.storage.copy_to_memory(job)`
(`spec_url`, `checks_json`, `delivery_url`, `demo_url`, `brand_url`, `pass_threshold`, plus `buyer`/`seller`).
Storage is inaccessible from nondet blocks, so the closures capture only `str` / `int` / `list` / `dict` values.
`scripts/preflight.py` and a simulated test both check that no `self` or storage object leaks into the closures.

## Leader (`evaluate()`)

1. Fetch `spec_url` and `delivery_url` with `gl.nondet.web.get`. Non-2xx, empty or failing fetches become the literal
   `FETCH_FAILED` (delivery) or **abort the leader** (spec: there is nothing to judge against).
2. If `demo_url` is set: `render(..., mode="html")` (truncated) and one `screenshot`. If `brand_url` is also set **and a
   demo screenshot exists**, add a brand screenshot. Never more than two images.
3. Truncate: spec 15000, delivery 15000, demo HTML 12000 characters.
4. `exec_prompt(..., response_format="json")` with a rubric prompt. Evidence sits in delimited blocks that are declared
   untrusted, and the delimiters are defanged inside the evidence so it cannot fake a block boundary.
5. **Normalize** the answer to the canonical shape: exactly the rubric's check ids, in rubric order (missing id =>
   `pass: false`, extra ids dropped), score clamped to an integer 0-100, string booleans coerced.
6. **Apply the deterministic rule** (below) and return `json.dumps(verdict, sort_keys=True)` containing only
   `score`, `passed`, `checks[{id, pass, note}]`.

## Validator (`validator_fn(leaders_res)`)

Rejects unless **all** of these hold:

| # | Condition |
|---|---|
| 1 | `leaders_res` is a `gl.vm.Return` |
| 2 | payload is a string that passes the strict schema check (exact keys, integer score 0-100, boolean `passed`, one entry per rubric id in rubric order) |
| 3 | the leader's `passed` equals what the deterministic rule computes from the leader's own score and checks |
| 4 | the validator's independent re-fetch + re-judgment succeeds and passes the same schema check |
| 5 | `passed` identical |
| 6 | `abs(score difference) <= 8` |
| 7 | every `checks[i].pass` identical (note wording is ignored) |

Condition 3 stops a leader from claiming a pass that the rules forbid *even if a validator's own result happens to
match the forged payload*. Both cases are covered by tests and mutation checks.

## Deterministic rule (after consensus, and also inside leader and validator)

```
passed = model_says_pass AND score >= pass_threshold AND every check with required=true passed
```

Applied to the leader's accepted payload again after consensus (idempotent), then the escrow is credited to the seller
(`passed`) or the buyer (`failed`).

## Known limits

* **Threshold straddle.** Scores 82 and 76 differ by only 6 (inside the tolerance) but land on opposite sides of a
  threshold of 80, so `passed` differs and validators disagree. That is deliberate (a false pass or fail is the whole
  risk), but it means a rubric whose true score sits near the threshold can fail to reach consensus. Pick a threshold
  with margin, and prefer objective, text-observable required checks.
* **Evidence drift.** Leader and validators fetch at different moments. Dynamic or rate-limited pages can make them
  disagree; the transaction then reverts and can be retried.
* **Screenshots add variance.** Keep visual checks optional (`required: false`) unless the rubric truly needs them.
* **LLM judgment is a judgment.** Consensus establishes that independent validators agree, not that the answer is right.

## What the simulated tests do and do not prove

`tests/simulated` runs the real contract source against an in-memory SDK stand-in with scripted web and LLM responses.
It proves the contract's own logic: settlement rules, state machine, payout accounting, schema and forgery checks,
evidence limits, and the two-image cap. It does **not** prove real validator behavior, real LLM behavior, or GenVM
sandbox semantics. That is what `docs/STUDIO_TEST_PLAN.md` and `tests/integration` are for.
