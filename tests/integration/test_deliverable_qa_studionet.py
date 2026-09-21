"""Disposable StudioNet lifecycle proof for DeliverableQA.

STATUS: written against the gltest 0.29.x API but NOT executed by the author (no network in the authoring
sandbox). Treat it as a starting point: run it once, fix any API drift, then record the resulting
transaction hashes in SUBMISSION.md. The authoritative logic checks are in tests/simulated.

    python -m pip install -r requirements-test.txt
    RUN_STUDIONET=1 gltest --network studionet tests/integration/test_deliverable_qa_studionet.py -s

Uses only example.org / example.com, which are permanent public pages (validators fetch from the internet).
"""
import json
import os
import unittest
from pathlib import Path

try:
    from gltest import get_contract_factory, create_account
    from gltest.assertions import tx_execution_succeeded
    HAVE_GLTEST = True
except Exception:  # pragma: no cover
    HAVE_GLTEST = False

ROOT = Path(__file__).resolve().parents[2]
PASS_RUBRIC = json.dumps(json.load(open(ROOT / "fixtures" / "rubrics" / "pass_example.json")))
FAIL_RUBRIC = json.dumps(json.load(open(ROOT / "fixtures" / "rubrics" / "fail_example.json")))


@unittest.skipUnless(HAVE_GLTEST and os.environ.get("RUN_STUDIONET") == "1",
                     "set RUN_STUDIONET=1 and install requirements-test.txt to run against StudioNet")
class TestStudioNetLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.buyer = create_account()
        cls.seller = create_account()
        factory = get_contract_factory("DeliverableQA")
        cls.buyer_view = factory.deploy(account=cls.buyer)
        cls.seller_view = cls.buyer_view.connect(cls.seller)

    def _run(self, job_id, rubric, delivery_url):
        r = self.buyer_view.open_escrow(
            args=[job_id, "https://example.org", rubric, "", "", 80]).transact(value=10)
        self.assertTrue(tx_execution_succeeded(r))
        r = self.seller_view.deliver(args=[job_id, delivery_url]).transact()
        self.assertTrue(tx_execution_succeeded(r))
        r = self.buyer_view.review(args=[job_id]).transact()
        self.assertTrue(tx_execution_succeeded(r))
        return json.loads(self.buyer_view.get_job(args=[job_id]).call())

    def test_pass_path_credits_seller(self):
        job = self._run("it-pass-1", PASS_RUBRIC, "https://example.com")
        self.assertEqual(job["status"], "passed")

    def test_fail_path_credits_buyer(self):
        job = self._run("it-fail-1", FAIL_RUBRIC, "https://example.com")
        self.assertEqual(job["status"], "failed")


if __name__ == "__main__":
    unittest.main()
