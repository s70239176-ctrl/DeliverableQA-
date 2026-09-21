# Consuming DeliverableQA from other contracts

DeliverableQA is a standalone primitive: no frontend, no backend. Other contracts (agent marketplaces, routers,
milestone payers) can read a job's outcome through its views.

> The interface below is a **sketch modeled on the `@gl.contract_interface` pattern** used in GenLayer docs. It has not
> been executed against a deployed instance. Verify against the current SDK before relying on it.

```python
@gl.contract_interface
class IDeliverableQA:
    class View:
        def get_status(self, job_id: str) -> str: ...
        def get_job(self, job_id: str) -> str: ...      # JSON string
```

Call it from **deterministic** contract code only. Cross-contract reads are not allowed inside nondet blocks.

## Views

| View | Returns |
|---|---|
| `get_status(job_id)` | `open` \| `delivered` \| `passed` \| `failed` \| `cancelled` (errors on unknown ids) |
| `get_job(job_id)` | JSON string (below) |
| `get_credit(addr)` | `u256` claimable balance |

```json
{
  "job_id": "job-pass-001",
  "buyer": "0x...", "seller": "0x...",
  "spec_url": "https://example.org",
  "checks": [{"id": "states_purpose", "required": true, "detail": "..."}],
  "demo_url": "", "brand_url": "", "delivery_url": "https://example.com",
  "pass_threshold": 80,
  "escrow": "0",
  "status": "passed", "score": 92, "passed": true,
  "result": {"checks": [{"id": "states_purpose", "note": "...", "pass": true}], "passed": true, "score": 92}
}
```

`escrow` is a decimal string because a `u256` can exceed JSON-safe integers.

## Recommended consumer checks

* Gate on `status == "passed"` (not merely `passed == true`), and read `result.checks` if a specific criterion matters.
* Compare `spec_url`, `checks` and `pass_threshold` with what your own logic approved. They are immutable after
  `open_escrow`, so a match today is a match forever.
* Treat `failed` and `cancelled` as final; treat `open` / `delivered` as pending.
* The verdict is only as strong as the evidence URLs. If your gate matters, require commit-pinned URLs.
