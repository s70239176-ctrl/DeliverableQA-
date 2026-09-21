#!/usr/bin/env python3
"""Mutation check: prove the test suite and the preflight actually have teeth.

    python scripts/mutation_check.py

For each mutant, a deliberately broken copy of the contract is written to a temp dir (the real contract
is never touched) and:
  * BEHAVIOUR mutants must make `tests/simulated` FAIL.
  * STATIC mutants must make `scripts/preflight.py` report at least one FAIL.
Exit code 0 only if every mutant is killed.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "contracts" / "deliverable_qa.py").read_text()

BEHAVIOUR = [
    ("validator tolerance 8 -> 30", "SCORE_TOLERANCE = 8", "SCORE_TOLERANCE = 30"),
    ("validator tolerance off-by-one", "> SCORE_TOLERANCE:", ">= SCORE_TOLERANCE:"),
    ("drop required-check rule", 'and int(verdict["score"]) >= threshold and all_required_ok', 'and int(verdict["score"]) >= threshold'),
    ("drop threshold rule", 'and int(verdict["score"]) >= threshold and all_required_ok', "and all_required_ok"),
    ("threshold > instead of >=", 'int(verdict["score"]) >= threshold', 'int(verdict["score"]) > threshold'),
    ("pay seller even on fail", "payee = seller if passed else buyer", "payee = seller"),
    ("pay buyer even on pass", "payee = seller if passed else buyer", "payee = buyer"),
    ("escrow not zeroed after verdict", '        job.escrow = u256(0)\n        job.status = "passed" if passed else "failed"', '        job.status = "passed" if passed else "failed"'),
    ("review allowed twice", 'if job.status != "delivered":', 'if job.status == "nonexistent":'),
    ("review allowed on open job", 'if job.status != "delivered":', 'if job.status == "passed":'),
    ("deliver allowed twice", 'if job.status != "open":\n            raise gl.vm.UserError("job is not open")', "pass"),
    ("cancel by anyone", "if gl.message.sender_address != job.buyer:", "if False:"),
    ("cancel refunds seller", "self._credit(job.buyer, job.escrow)", "self._credit(job.seller, job.escrow)"),
    ("validator ignores check flips", 'if a["id"] != b["id"] or a["pass"] != b["pass"]:', "if False:"),
    ("validator ignores passed flag", 'if leader["passed"] != mine["passed"]:', "if False:"),
    ("validator skips leader rule check", 'if _apply_rules(leader, checks, threshold)["passed"] != leader["passed"]:', "if False:"),
    ("prompt delimiters not defanged", 'return text.replace("<<<", "<<").replace(">>>", ">>")', "return text"),
    ("brand image sent without demo screenshot", 'if brand_url != "" and len(images) == 1:', 'if brand_url != "":'),
    ("withdraw does not zero credit", "self.credits[sender] = u256(0)              # effects first", "pass"),
    ("zero escrow allowed", "if int(value) == 0:", "if False:"),
    ("localhost allowed", 'if host == "" or host == "localhost" or host.endswith(".localhost"):', 'if host == "":'),
    ("spec fetch failure ignored", 'raise gl.vm.UserError("spec_url could not be fetched")', 'spec_text = ""'),
    ("non-2xx accepted as evidence", "if isinstance(code, int) and (code < 200 or code >= 300):", "if False:"),
    ("missing model check counted as pass", '"pass": False, "note": "missing from model output"', '"pass": True, "note": "missing from model output"'),
]

STATIC = [
    ("Depends hash typo (extra h)", "mwsfhh8jpz09h6", "mwsfhhh8jpz09h6"),
    ("int in storage", "    credits: TreeMap[Address, u256]", "    credits: TreeMap[Address, u256]\n    counter: int"),
    ("bare TreeMap", "    jobs: TreeMap[str, Job]", "    jobs: TreeMap"),
    ("strict_eq used", "raw = gl.vm.run_nondet_unsafe(evaluate, validator_fn)", "raw = gl.eq_principle.strict_eq(evaluate)"),
    ("web call outside evaluator", "        ids = [c[\"id\"] for c in checks]\n\n        evaluate", "        _x = gl.nondet.web.get(spec_url)\n        ids = [c[\"id\"] for c in checks]\n\n        evaluate"),
    ("self inside validator factory", '    ids = [c["id"] for c in checks]\n\n    def validator_fn', '    ids = [c["id"] for c in checks]\n    _s = self\n\n    def validator_fn'),
    ("payable on deliver", "    @gl.public.write\n    def deliver", "    @gl.public.write.payable\n    def deliver"),
    ("unannotated public argument", "def deliver(self, job_id: str, delivery_url: str)", "def deliver(self, job_id, delivery_url: str)"),
    ("decorated constructor", "    def __init__(self):", "    @gl.public.write\n    def __init__(self):"),
    ("undeclared self field", '        print("[DeliverableQA] deployed")', "        self.oops = 1"),
    ("transfer outside withdraw", '        job.escrow = u256(0)\n        job.status = "cancelled"', '        job.escrow = u256(0)\n        _Recipient(job.buyer).emit_transfer(value=u256(1))\n        job.status = "cancelled"'),
    ("storage write before nondet", "        evaluate = _make_evaluator(", '        job.status = "reviewing"\n        evaluate = _make_evaluator('),
]


def mutate(old, new, tmp):
    if old not in SRC:
        sys.exit("mutation target not found (contract changed?): %r" % old)
    path = Path(tmp) / "mutant.py"
    path.write_text(SRC.replace(old, new, 1))
    return path


def main():
    survivors = []
    with tempfile.TemporaryDirectory() as tmp:
        print("== behaviour mutants: tests/simulated must FAIL ==")
        for name, old, new in BEHAVIOUR:
            env = dict(os.environ, DQA_CONTRACT_PATH=str(mutate(old, new, tmp)))
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests" / "simulated")],
                               env=env, capture_output=True, text=True)
            killed = r.returncode != 0
            print(("KILLED   " if killed else "SURVIVED ") + name)
            if not killed:
                survivors.append(name)
        print("\n== static mutants: scripts/preflight.py must FAIL ==")
        for name, old, new in STATIC:
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "preflight.py"), str(mutate(old, new, tmp))],
                               capture_output=True, text=True)
            caught = r.returncode != 0 and "Traceback" not in r.stderr
            print(("CAUGHT   " if caught else "MISSED   ") + name)
            if not caught:
                survivors.append(name)
    total = len(BEHAVIOUR) + len(STATIC)
    print("\n%d/%d mutants killed" % (total - len(survivors), total))
    sys.exit(1 if survivors else 0)


if __name__ == "__main__":
    main()
