# Submission notes

Reviewer-oriented summary of what DeliverableQA is, what is verified, and what still needs on-chain evidence.

## One-paragraph summary

DeliverableQA is a single-file GenLayer Intelligent Contract: escrow plus a quality court for agent-to-agent deliveries.
A buyer locks GEN with an immutable acceptance rubric; a seller submits public URLs; `review()` has GenLayer validators
fetch live evidence and reach consensus on pass/fail; the escrow is credited to exactly one party and withdrawn with a
pull payment.

## Why it belongs on GenLayer

The decision is contested and subjective ("does this README cover install and run?"), both parties are adversarial, and a
false pass or false fail moves real money. A normal contract cannot read the delivery; a centralized service would be a
single trusted judge. Validators independently re-fetching evidence and re-judging it is exactly the primitive needed.

## Deterministic vs consensus

| Deterministic (plain contract code) | Consensus (validators) |
|---|---|
| Input validation, URL policy, rubric schema | Fetching spec / delivery / demo evidence |
| Escrow, credits, withdrawals, state machine | Judging the delivery against the rubric |
| Settlement rule (score, threshold, required checks) | Agreeing on `passed`, score (+/-8) and per-check verdicts |

## Verification status (be precise)

| Claim | Evidence | Status |
|---|---|---|
| Static invariants (Depends hash, storage types, decorators, nondet rules, no `strict_eq`) | `python scripts/preflight.py` | 78/78 checks pass |
| Settlement truth table | `python scripts/local_helper_check.py` | 40/40 checks pass |
| Contract logic against a fake SDK (state machine, payouts, consensus predicate, forgery, evidence limits, fund conservation) | `python -m unittest discover -s tests/simulated` | 56/56 tests pass |
| The tests and preflight actually have teeth | `python scripts/mutation_check.py` | 36/36 deliberate bugs caught |
| Runs correctly on real GenVM / real validators / real LLMs | Studio test plan, `tests/integration` | **NOT YET DONE** |

The simulated suite cannot prove GenVM sandbox semantics, real validator behavior or real LLM output quality.
Anything marked "not yet done" must be filled in with real transaction evidence before it is claimed.

## On-chain evidence (fill in after deploying)

| Item | Value |
|---|---|
| Network | StudioNet (or as deployed) |
| Contract address | `TBD` |
| Deploy transaction | `TBD` |
| Deployer | `TBD` |
| Run 1 (PASS) `open_escrow` / `deliver` / `review` tx | `TBD` |
| Run 2 (FAIL) `open_escrow` / `deliver` / `review` tx | `TBD` |
| Run 3 (cancel) tx | `TBD` |
| Validator votes on the `review` transactions | `TBD` |

Follow [docs/STUDIO_TEST_PLAN.md](docs/STUDIO_TEST_PLAN.md) to produce these.

## Known limitations

- **Seller slot is first-come**: whoever calls `deliver` first is the seller. Pinning a seller needs one more argument.
- **Live evidence**: URL contents can change after `deliver`. Use commit-pinned URLs to freeze them.
- **Threshold straddle**: a true score near `pass_threshold` can fail consensus (by design; see docs/CONSENSUS.md).
- **No timeouts or appeals**: an unreviewed delivered job stays locked; accepted verdicts are final.
- **`emit_transfer` in Studio**: payout uses the official EVM-interface transfer; if Studio's local ledger rejects it,
  credit accounting is still correct and only the payout call fails.
- **Depends hash**: the file uses the hash published in the GenLayer docs. If Studio's boilerplate differs, copy Studio's.
