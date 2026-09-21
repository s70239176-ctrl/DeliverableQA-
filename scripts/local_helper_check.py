#!/usr/bin/env python3
"""Deterministic checks of the contract's pure helpers, without GenVM, network or pytest.

    python scripts/local_helper_check.py

Loads contracts/deliverable_qa.py against the in-memory SDK stand-in in tests/simulated/fake_genlayer.py.
"""
import io
import contextlib
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "simulated"))
import fake_genlayer as fg  # noqa: E402

mod = fg.load_contract()
failures = 0


def expect(name, got, want):
    global failures
    if got == want:
        print("PASS  " + name)
    else:
        failures += 1
        print("FAIL  %s -> got %r, want %r" % (name, got, want))


# 1. every shipped rubric is a valid rubric
for p in sorted((ROOT / "fixtures" / "rubrics").glob("*.json")):
    expect("rubric parses: " + p.name, len(mod._parse_checks(p.read_text())) >= 1, True)

# 2. settlement truth table: passed == model_pass AND score >= threshold AND all required checks pass
checks = mod._parse_checks((ROOT / "fixtures" / "rubrics" / "pass_example.json").read_text())  # 2 required + 1 optional
for model_pass, score, c1, c2, c3 in itertools.product((True, False), (79, 80), (True, False), (True, False), (True, False)):
    v = {"score": score, "passed": model_pass, "checks": [
        {"id": "states_purpose", "pass": c1, "note": ""},
        {"id": "has_info_link", "pass": c2, "note": ""},
        {"id": "mentions_operations", "pass": c3, "note": ""}]}
    want = model_pass and score >= 80 and c1 and c2          # c3 is optional
    expect("rules model=%s score=%d req=%s/%s opt=%s" % (model_pass, score, c1, c2, c3),
           mod._apply_rules(v, checks, 80)["passed"], want)

# 3. rules are idempotent (validators re-apply them to the leader's payload)
v = {"score": 90, "passed": True, "checks": [{"id": i["id"], "pass": True, "note": ""} for i in checks]}
once = mod._apply_rules(v, checks, 80)
expect("rules idempotent", mod._apply_rules(once, checks, 80), once)

# 4. canonical verdict round-trips through the strict parser
ids = [c["id"] for c in checks]
raw = json.dumps(once, sort_keys=True)
expect("strict parser accepts canonical verdict", mod._parse_verdict(raw, ids) == once, True)
expect("strict parser rejects reordered ids", mod._parse_verdict(raw, list(reversed(ids))), None)

print("\n%s" % ("ALL OK" if not failures else "%d FAILED" % failures))
sys.exit(1 if failures else 0)
