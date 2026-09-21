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
| Deploys and runs on GenLayer Studio: constructor, full pass / fail / cancel lifecycles, payouts | Explorer transactions below (19 txs, all FINALIZED, consensus Accepted) | **Observed on-chain** |
| Verdict contents (score, per-check results) and validator votes for each `review` | `get_job` output and the explorer's per-transaction consensus view | **NOT YET CAPTURED** |

The simulated suite cannot prove GenVM sandbox semantics, real validator behavior or real LLM output quality.
Anything marked "not yet done" must be filled in with real transaction evidence before it is claimed.

## On-chain evidence

Network: GenLayer Studio. Contract: `0x68f71EB90825cb3b7759fb62b2E96c68A68Cc39e`
([explorer](https://explorer-studio.genlayer.com/address/0x68f71EB90825cb3b7759fb62b2E96c68A68Cc39e)).
Deploy: `0xccb520cd68a16e134aad7f332701b202dee5aecf8108fa7325d50dfc4f0838c3` (constructor SUCCESS), created
Sep 20, 2026 11:30:44 PM, deployer `0x790695eE6E46E813B99c50069C0e608ACD1a7E3a`.

The explorer lists **19 transactions, all FINALIZED with consensus result Accepted**. The tables below are transcribed from the
contract's explorer page. **Which job and which outcome each row belongs to is inferred from call order, callers and payouts;**
the verdict JSON and validator votes are not shown on that page and are still to be captured (see the last section).

Accounts: `A` = `0x790695...1a7E3a`, `B` = `0x3779aE...507644`, `C` = `0x5F5128...b5Fc58`.

| Job (inferred) | Step | Caller | Method | Result | Tx |
|---|---|---|---|---|---|
| 1 (pass) | open_escrow | A (buyer) | `open_escrow` | SUCCESS | `0xe7a1225b2f6504860c4ef43e462a2ac79e7f602807b5f116237c0056e3d0a3ba` |
| | deliver | C (seller) | `deliver` | SUCCESS | `0xb1e475924b8914cff332547f3cc0be1bae93fc3bab09d470c5221b40d0edb71f` |
| | review | B (third party) | `review` | SUCCESS | `0x2a01cd3f42c783e843ee07194c7d8023b5bc4f86012717f20b46536deca1a35f` |
| | withdraw | C | `withdraw` | SUCCESS | `0x23c8a4421058ccbf61d307a7eddd7f36ca9dec405dadc904e078afc606b98890` |
| | payout to C | contract | Send OUT | FINALIZED | `0x1faf751c302b3cf8cccacddd53836b65d63268abfff35d4ef843dde8625e2c85` |
| 2 (fail) | open_escrow | B (buyer) | `open_escrow` | SUCCESS | `0xf7768a27547897742ec3e66164102164737d43b37f9a9f666051c37ee3856177` |
| | deliver | C | `deliver` | SUCCESS | `0x08e667b3e200eac213b358b1023674a23b2e4b618c2e5590e43087a777c5f05b` |
| | review | C | `review` | SUCCESS | `0x8dda7be7a1ca67bbc1a0518844506983bf12968fcb71d56fe36be543342196fc` |
| | withdraw | B | `withdraw` | SUCCESS | `0x8a096e46af3d6029f543aa118fb8b272a25d33b0ccb2b5ac8a66d650532654df` |
| | payout to B | contract | Send OUT | FINALIZED | `0xdddcd277985d6e2cb8673d124144c9d0c9f349178e92d91cb3c5265b10e3f4d9` |
| 3 (cancel) | open_escrow | B | `open_escrow` | SUCCESS | `0x3d38ab0da2801ef8f6c9e85a5e84682ec535ef2f70b0f9eb8ed85341b4eebdf8` |
| | cancel | B | `cancel` | SUCCESS | `0x4b4ea3a33a671333bf908b127575870102e1dca7feecbfa4cd0f8fffcd68a0da` |
| 4 (pass) | open_escrow | B | `open_escrow` | SUCCESS | `0x089fbc211802b8f7a1dc0a0245c609cb54a98f49f5abfed10bc4c22c80bdf649` |
| | deliver | C | `deliver` | SUCCESS | `0x2d4b6b315f06958d049e58b9e1cad331db35363dc260080be56f69acee9a5f39` |
| | review | C | `review` | SUCCESS | `0x8c7420707cd5430719d3f7679e011a7a9ab4ec93fa487346743f6cd059338f5a` |
| | withdraw | C | `withdraw` | SUCCESS | `0x63db21ff841f497bdc8e7408db01da3fec6d205f040055f5608e24f935fc483d` |
| | payout to C | contract | Send OUT | FINALIZED | `0xe3dcbc083cbcb727e3a40edacf8d27a8e8314944a88dc7a03fd90148172ecc1b` |
| negative | withdraw with nothing left | C | `withdraw` | GenVM ERROR (expected), consensus Accepted | `0x6ae3992142506e520965eaf49afda9404de195e6a2bf3e1d4352b8b64f778e64` |

What this shows (and no more):

* The contract deploys and every public method executed on Studio, with review transactions reaching consensus (Accepted).
* Seller payouts (jobs 1 and 4) and a buyer refund (job 2) were paid out by `withdraw` as real `Send` transactions, so the
  `emit_transfer` payout path works in Studio.
* A repeated `withdraw` errors at the GenVM level, as designed (`nothing to withdraw`).
* Job 1 was reviewed by a third party and job 2 by the seller, matching "anyone may call `review`".
* Account B has no `withdraw` after the job 3 cancel, so that refund appears unclaimed.

### Still to capture before calling this complete

1. `get_job` output for jobs 1-4 (status, score, `result_json`) to confirm each outcome, since pass/fail above is inferred from who was paid.
2. Validator votes and the leader/validator agreement for at least one `review` (the explorer's per-transaction consensus view).
3. The exact `job_id`, URLs and rubric used for each job.

## Known limitations

- **Seller slot is first-come**: whoever calls `deliver` first is the seller. Pinning a seller needs one more argument.
- **Live evidence**: URL contents can change after `deliver`. Use commit-pinned URLs to freeze them.
- **Threshold straddle**: a true score near `pass_threshold` can fail consensus (by design; see docs/CONSENSUS.md).
- **No timeouts or appeals**: an unreviewed delivered job stays locked; accepted verdicts are final.
- **`emit_transfer` in Studio**: payout uses the official EVM-interface transfer; if Studio's local ledger rejects it,
  credit accounting is still correct and only the payout call fails.
- **Depends hash**: the file uses the hash published in the GenLayer docs. If Studio's boilerplate differs, copy Studio's.
