# Studio manual test plan

Everything here uses only `example.org` / `example.com`: permanent public pages, tiny, and stable. Their wording has
changed over the years, so every check describes the *meaning* of the text instead of quoting it.

Type values into Studio's argument boxes **without surrounding quotes**. Paste `checks_json` as one line.
Do not use `localhost` or private-IP URLs: validators fetch from the public internet.

## Setup

1. Deploy `contracts/deliverable_qa.py`. The constructor takes no arguments.
2. Two accounts: **Buyer (A)**, funded from the faucet, and **Seller (B)**.
3. `review` takes a while (validators fetch and judge independently). Wait for finalization before `get_job`.

## Run 1 - expected PASS (seller paid)

As **Buyer (A)**, `open_escrow` with a nonzero value (e.g. `10`):

```
job_id:         job-pass-001
spec_url:       https://example.org
checks_json:    [{"id":"states_purpose","required":true,"detail":"Delivery text states that the page or domain is meant for use in documentation or illustrative examples"},{"id":"has_info_link","required":true,"detail":"Delivery contains a link to further information (for example a 'Learn more' or 'More information' link)"},{"id":"mentions_operations","required":false,"detail":"Delivery advises against using it in real operations or production"}]
demo_url:       (empty)
brand_url:      (empty)
pass_threshold: 80
```

As **Seller (B)**: `deliver("job-pass-001", "https://example.com")`.
Any account: `review("job-pass-001")`, then `get_job` / `get_status`.

Expect `status: "passed"`, `passed: true`, score roughly 85-100. The optional `mentions_operations` check may be true or
false depending on the page's current wording; that is intentional (an optional miss must not block a pass).
As **Seller (B)**: `get_credit(<seller address from get_job>)` equals the escrow; `withdraw()`; `get_credit` is `0`.

## Run 2 - expected FAIL (buyer refunded)

As **Buyer (A)**, `open_escrow` with a nonzero value:

```
job_id:         job-fail-001
spec_url:       https://example.org
checks_json:    [{"id":"readme_covers","required":true,"detail":"Delivery explains how to install and how to run the demo"},{"id":"example_http","required":true,"detail":"Delivery documents GET /v1/quote returning mid and ask"}]
demo_url:       (empty)
brand_url:      (empty)
pass_threshold: 80
```

As **Seller (B)**: `deliver("job-fail-001", "https://example.com")` (nothing about installs or a quote endpoint).
Any account: `review("job-fail-001")`.

Expect `status: "failed"`, `passed: false`, both checks false, buyer credited. As Buyer: `get_credit`, then `withdraw()`.

## Run 3 - cancel before delivery

```
job_id:         job-cancel-001
spec_url:       https://example.org
checks_json:    [{"id":"any_check","required":true,"detail":"Delivery is relevant to the spec"}]
demo_url:       (empty)
brand_url:      (empty)
pass_threshold: 70
```

Then `cancel("job-cancel-001")` as the same buyer. `get_status` is `cancelled`; `get_credit(buyer)` shows the refund.

## Run 4 (optional) - screenshot + brand image

Only after Runs 1-2 work: screenshots are slower and add validator variance.

```
job_id:         job-brand-001
spec_url:       https://example.org
checks_json:    [{"id":"states_purpose","required":true,"detail":"Delivery text states that the page is meant for documentation or illustrative examples"},{"id":"screenshot_brand","required":false,"detail":"Demo page visually resembles the brand reference image (same layout and colors)"}]
demo_url:       https://example.com
brand_url:      https://example.org
pass_threshold: 80
```

Seller delivers `https://example.com`; anyone calls `review`. Expect a pass.

## Negative tests (each must fail with a clear error)

| Call | Expected error |
|---|---|
| `open_escrow` with value 0 | `escrow required` |
| `open_escrow` reusing `job-pass-001` | `job_id already exists` |
| `open_escrow` with `demo_url` = `http://localhost:3000` | `demo_url must be a public http(s) URL...` |
| `open_escrow` with `checks_json` = `[]` | `checks_json must be a JSON list...` |
| `open_escrow` with `pass_threshold` = `0` or `101` | `pass_threshold must be 1-100` |
| `review` on an `open` job | `job is not in delivered state...` |
| `deliver` twice on the same job | `job is not open` |
| `review` twice on the same job | `job is not in delivered state...` |
| `cancel` from Seller (B) | `only the buyer can cancel` |
| `cancel` after `deliver` | `only an open (undelivered) job can be cancelled` |
| `withdraw` with no credit | `nothing to withdraw` |

All of these are also asserted in `tests/simulated`.

## Reading the `review` transaction

The leader output is one line of canonical JSON:

```json
{"checks":[{"id":"states_purpose","note":"...","pass":true},{"id":"has_info_link","note":"...","pass":true},{"id":"mentions_operations","note":"...","pass":false}],"passed":true,"score":92}
```

Validator votes should be agree. If they disagree, retry once (fetches occasionally flake), then confirm both URLs load
in a private browser window. A rubric whose true score sits near `pass_threshold` can legitimately fail consensus; see
[CONSENSUS.md](CONSENSUS.md#known-limits).

## If Studio errors, check these

1. **Depends hash**: line 1 must match Studio's current boilerplate exactly (`python scripts/preflight.py` checks length and the docs hash).
2. **Storage types**: fields must be `DynArray`, fully specialized `TreeMap[K, V]`, `u256` or `u32`. Never `list`, `dict`, `int`.
3. **Undeclared fields**: every persistent field needs a class-body annotation; `self.x = ...` alone creates nothing.
4. **Storage inside nondet**: `evaluate` / `validator_fn` may touch only plain values copied out via `copy_to_memory`.
5. **Payable decorator**: only `open_escrow` is payable; value sent to any other method is rejected.
6. **Value vs fee**: Studio's value field is GEN sent to the contract (`gl.message.value`), not gas. Zero fails with `escrow required`.
7. **Unfetchable URLs**: localhost, private IPs, or bot-blocking pages fail `review`. If `spec_url` fails, the tx reverts and the job stays `delivered`, so retry.
8. **Validators disagree**: flaky or JS-heavy demo pages, or a score near the threshold. Use small static raw-text URLs first.
9. **Address format**: `get_credit` needs a valid `0x` address exactly as Studio shows it.
10. **`withdraw()` errors**: if Studio's local ledger rejects `emit_transfer`, credit accounting is still correct; only the payout call fails (a Studio simulation limit).
