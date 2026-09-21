# Rubric (`checks_json`) format

`checks_json` is a JSON **list of objects**, stored verbatim and immutable after `open_escrow`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string, 1-64 chars, unique in the list | yes | Stable key; the verdict reports one entry per id, in this order |
| `required` | boolean | no (default `true`) | If a required check fails, the job fails regardless of score |
| `detail` | string (truncated to 500 chars) | no | The criterion the judge applies |

Limits: at most **20** checks, at most **6000** characters of JSON. `open_escrow` rejects anything else.

## Example (`fixtures/rubrics/quote_api_example.json`)

```json
[
  {"id": "readme_covers", "required": true, "detail": "README explains install and how to run the demo"},
  {"id": "example_http", "required": true, "detail": "Delivery text or live demo documents GET /v1/quote returning mid and ask"},
  {"id": "screenshot_brand", "required": false, "detail": "Demo page uses the brand colors / layout if brand_url and demo_url set"}
]
```

## Authoring guidance

* Write checks a validator can decide from **fetched text or the attached screenshot**. The judge is instructed never to
  invent endpoints, files or behavior, and to fail any check whose evidence is missing.
* Make **required** checks objective and text-observable. Keep taste-based or visual checks optional.
* Choose `pass_threshold` with margin below the score a good delivery will earn, so honest scoring noise cannot straddle it.
* Ids are the consensus key: keep them short, lowercase, and free of spaces.
* Prefer content-addressed URLs (commit-pinned raw files) so the evidence cannot change after `deliver`.

## Verdict shape (`result_json`)

```json
{"checks":[{"id":"readme_covers","note":"README has install and run sections","pass":true}],"passed":true,"score":86}
```

Keys are sorted, notes are informational only (never compared by validators), and `passed` already reflects the
deterministic rule.
