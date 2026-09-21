# DeliverableQA

**Escrow + a quality court for agent-to-agent delivery of code, docs and optional UI, on GenLayer.**

DeliverableQA answers a question that a normal escrow cannot:
> Did the seller actually deliver what the buyer's acceptance rubric asked for?

It is a **standalone Intelligent Contract**, not an application. There is intentionally **no frontend and no backend
service**. Buyers, sellers, agents, marketplaces and other contracts interact with the contract directly.

## Why this exists

Agents increasingly pay each other for work products: a client library, a spec, a demo page. Payment logic is easy.
Judging the work is not, and whoever judges holds the money:

- a **false pass** lets the seller keep payment for bad work;
- a **false fail** lets the buyer keep the funds after seeing the work;
- a centralized judge (one server, one model) is a single party both sides must trust.

DeliverableQA splits the problem:

1. **Deterministic escrow** locks GEN and an *immutable* rubric before any work is delivered.
2. **GenLayer consensus** fetches live public evidence and has independent validators judge it against the rubric.
3. **Deterministic settlement** applies fixed rules to the accepted verdict and credits exactly one party.
4. **Pull-pattern payout**: `withdraw()` is the only place value leaves the contract.

## Lifecycle

```
open_escrow            deliver                     review
buyer locks GEN  -->   seller submits URLs   -->   anyone triggers
+ rubric + threshold                                validators fetch spec / delivery / demo,
     |                                              judge, and reach consensus
     | cancel (buyer, before delivery)                      |
     v                                          +-----------+-----------+
 cancelled  (buyer credited)                    v                       v
                                             passed                  failed
                                         (seller credited)       (buyer credited)
                                                   \                   /
                                                    +---- withdraw ---+
```

## Settlement rule

```
passed = model_says_pass  AND  score >= pass_threshold  AND  every check with required=true passed
```

The LLM never decides settlement alone. A failed required check or a low score forces `failed` even if the model says
"pass". Optional checks (`required: false`) inform the score but never block a pass on their own.

## What consensus actually does

`review()` runs **one** consensus boundary with `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)` (never `strict_eq`).

- The **leader** fetches the spec and delivery, optionally renders a demo page (+ screenshot, + brand image; at most two
  images), asks the LLM for structured JSON, then normalizes it to exactly the rubric's check ids.
- Every **validator** independently re-fetches and re-judges, then accepts only if `passed` is identical, the score is
  within 8 points, and every per-check verdict matches. Note wording is ignored.
- Validators also reject a leader payload that claims a pass the deterministic rule forbids.

Details and known limits: [docs/CONSENSUS.md](docs/CONSENSUS.md).

## Rubric

`checks_json` is a JSON list, immutable after `open_escrow`:

```json
[
  {"id": "readme_covers", "required": true, "detail": "README explains install and how to run the demo"},
  {"id": "example_http", "required": true, "detail": "Delivery text or live demo documents GET /v1/quote returning mid and ask"},
  {"id": "screenshot_brand", "required": false, "detail": "Demo page uses the brand colors / layout if brand_url and demo_url set"}
]
```

See [docs/RUBRIC_FORMAT.md](docs/RUBRIC_FORMAT.md). The judge evaluates **only fetched text and images** and must fail any
check whose evidence is missing.

## Public interface

| Method | Kind | Purpose |
|---|---|---|
| `open_escrow(job_id, spec_url, checks_json, demo_url, brand_url, pass_threshold)` | write, **payable** | Lock GEN + rubric. Rejects zero value. |
| `deliver(job_id, delivery_url)` | write | Submit the public delivery URL; caller becomes the seller. |
| `review(job_id)` | write | Consensus verdict on a delivered job. Anyone may call; once per job. |
| `cancel(job_id)` | write | Buyer only, before delivery. |
| `withdraw()` | write | Pay out the caller's credits. |
| `get_job(job_id)` / `get_status(job_id)` / `get_credit(addr)` | view | Read state (`get_job` returns a JSON string). |

Every argument and return type is `str`, `bool`, `Address`, `u256` or `u32`, so Studio renders a plain form.

## State design

Two persistent fields: `jobs: TreeMap[str, Job]` and `credits: TreeMap[Address, u256]`. `Job` is an
`@allow_storage @dataclass`. Nothing uses `list`, `dict` or `int` in storage. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Security properties

- Public `http(s)` URLs only: localhost, private ranges and non-http schemes are rejected at input time.
- Fetched pages are **untrusted data**: evidence is delimited, delimiters are defanged inside it, and the prompt forbids
  following instructions found in evidence.
- The leader's output is re-derived by validators, not trusted; the payload is schema-checked and rule-checked.
- Missing or failed evidence fails the affected checks (`FETCH_FAILED` is never treated as a pass). If the **spec**
  cannot be fetched the transaction reverts and the job stays `delivered`, so `review` can be retried.
- No storage access, no value transfer and no nested nondet inside the nondet blocks. Storage is copied out first.
- Value moves only in `withdraw()`, after the credit is zeroed. Conservation of funds is tested.
- Rubric, URLs and threshold are immutable after `open_escrow`. The content behind the URLs is live; use commit-pinned
  URLs to freeze it.

## Repository layout

```
contracts/deliverable_qa.py         Intelligent Contract (single file, paste into Studio)
fixtures/rubrics/                   Example rubrics used by tests and the Studio test plan
scripts/preflight.py                Static invariant checks (Depends hash, storage types, nondet rules, ...)
scripts/local_helper_check.py       Deterministic settlement truth-table checks without GenVM
scripts/mutation_check.py           Proves the tests and preflight catch 36 deliberate contract bugs
scripts/deploy_studionet.sh         Minimal StudioNet deploy helper
tests/simulated/                    56 tests against an in-memory SDK stand-in (stdlib only)
tests/integration/                  StudioNet lifecycle test (gltest) - not yet executed, see file header
docs/ARCHITECTURE.md                State machine, storage, value flow, design limits
docs/CONSENSUS.md                   Leader/validator equivalence design and known limits
docs/RUBRIC_FORMAT.md               checks_json specification and authoring guidance
docs/INTEGRATION.md                 Reading job outcomes from other contracts
docs/STUDIO_TEST_PLAN.md            Copy-paste Studio runs, negative tests, error checklist
SUBMISSION.md                       Reviewer-oriented notes and evidence checklist
```

## Tests

No installs are needed for the local suite (Python standard library only):

```
python scripts/preflight.py                          # 78 static invariant checks
python scripts/local_helper_check.py                 # 40 settlement truth-table checks
python -m unittest discover -s tests/simulated -v    # 56 simulated contract tests
python scripts/mutation_check.py                     # 36/36 deliberate bugs must be caught
```

The simulated suite runs the real contract file against a scripted web/LLM and a fake SDK. It proves the contract's own
logic, **not** real validator or LLM behavior. Real-network proof is `docs/STUDIO_TEST_PLAN.md` (manual, in Studio) and
the StudioNet lifecycle test:

```
python -m pip install -r requirements-test.txt
RUN_STUDIONET=1 gltest --network studionet tests/integration/test_deliverable_qa_studionet.py -s
```

## Deployment

Single contract, no service dependency:

```
genlayer network set studionet
genlayer deploy --contract contracts/deliverable_qa.py
```

or paste `contracts/deliverable_qa.py` into GenLayer Studio and deploy with no constructor arguments.

Deployment evidence (contract address, deploy transaction, lifecycle transactions) is recorded in
[`SUBMISSION.md`](SUBMISSION.md) once the contract has been deployed.

## Why this is a primitive, not an app

DeliverableQA does not run agents, host deliverables or provide a dashboard. It answers one reusable shared-state
question: **did this exact delivery meet this exact rubric, and who got paid?** Marketplaces, agent routers, milestone
payers and other Intelligent Contracts can consume that outcome without trusting a centralized judge.

## License

MIT
