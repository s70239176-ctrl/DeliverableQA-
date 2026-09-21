"""In-memory stand-in for the GenLayer SDK.

Just enough surface to execute contracts/deliverable_qa.py in plain CPython:
  * storage types (TreeMap, DynArray, u256, u32, Address, @allow_storage)
  * message context (sender / value) and payable enforcement
  * scripted web + LLM (gl.nondet.web.get / render, gl.nondet.exec_prompt)
  * gl.vm.run_nondet_unsafe with a leader run and a validator run
  * an emit_transfer recorder

It does NOT simulate GenVM sandboxing, real validator sets, or real consensus.
It exists to prove the contract's own logic. Real-network proof lives in
tests/integration and docs/STUDIO_TEST_PLAN.md.
"""
import contextlib
import dataclasses
import importlib.util
import os
import sys
import types
from pathlib import Path

CONTRACT_PATH = Path(os.environ.get(
    "DQA_CONTRACT_PATH",
    str(Path(__file__).resolve().parents[2] / "contracts" / "deliverable_qa.py")))


class UserError(Exception):
    pass


class Return:
    def __init__(self, calldata):
        self.calldata = calldata


class Address:
    def __init__(self, value):
        if isinstance(value, Address):
            value = value.as_hex
        if not (isinstance(value, str) and value.startswith("0x") and len(value) == 42):
            raise ValueError("bad address")
        int(value, 16)
        self.as_hex = value.lower()

    def __eq__(self, other):
        return isinstance(other, Address) and self.as_hex == other.as_hex

    def __hash__(self):
        return hash(self.as_hex)

    def __repr__(self):
        return "Address(%r)" % self.as_hex

    def __lt__(self, other):
        return self.as_hex < other.as_hex


class u256(int):
    pass


class u32(int):
    pass


class TreeMap(dict):
    def __class_getitem__(cls, item):
        return cls


class DynArray(list):
    def __class_getitem__(cls, item):
        return cls


def allow_storage(cls):
    return cls


class _Runtime:
    def __init__(self):
        self.reset()

    def reset(self):
        self.pages = {}          # url -> (status_code, bytes)   for web.get
        self.rendered = {}       # url -> html str               for web.render(mode="html")
        self.screenshots = {}    # url -> bytes                  for web.render(mode="screenshot")
        self.llm = None          # callable(prompt, response_format, images) -> dict | str
        self.llm_calls = []      # one record per exec_prompt call
        self.transfers = []      # (Address, int) recorded by emit_transfer
        self.sender = None
        self.value = u256(0)
        self.in_nondet = False


RT = _Runtime()


def _require_nondet():
    if not RT.in_nondet:
        raise RuntimeError("gl.nondet.* called outside a nondet block (would be an error on GenVM)")


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self.body = body


class _Web:
    def get(self, url, **kwargs):
        _require_nondet()
        if url not in RT.pages:
            raise RuntimeError("fake web: no page for " + url)
        status, body = RT.pages[url]
        return _Resp(status, body)

    def render(self, url, mode="text", **kwargs):
        _require_nondet()
        if mode == "screenshot":
            if url not in RT.screenshots:
                raise RuntimeError("fake web: no screenshot for " + url)
            return RT.screenshots[url]
        if url not in RT.rendered:
            raise RuntimeError("fake web: no rendered page for " + url)
        return RT.rendered[url]


def _exec_prompt(prompt, response_format="text", images=None):
    _require_nondet()
    if images is not None and len(images) > 2:
        raise ValueError("exec_prompt accepts at most two images")
    RT.llm_calls.append({
        "prompt": prompt,
        "images": list(images or []),
        "images_kwarg_passed": images is not None,
        "response_format": response_format,
    })
    if RT.llm is None:
        raise RuntimeError("fake LLM not configured")
    return RT.llm(prompt, response_format, images)


def _run_nondet_unsafe(leader_fn, validator_fn):
    RT.in_nondet = True
    try:
        try:
            leader_res = Return(leader_fn())
        except Exception as exc:  # leader failure: validators see a non-Return
            leader_res = exc
        agreed = validator_fn(leader_res)
    finally:
        RT.in_nondet = False
    if not isinstance(leader_res, Return):
        raise leader_res
    if not agreed:
        raise UserError("consensus not reached: validators disagreed with the leader")
    return leader_res.calldata


class _Contract:
    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        for name, tp in getattr(cls, "__annotations__", {}).items():
            if tp is TreeMap:
                setattr(obj, name, TreeMap())
            elif tp is DynArray:
                setattr(obj, name, DynArray())
        return obj


def _view(fn):
    fn._gl_kind = "view"
    return fn


class _Write:
    def __call__(self, fn):
        fn._gl_kind = "write"
        return fn

    @staticmethod
    def payable(fn):
        fn._gl_kind = "payable"
        return fn


def _contract_interface(cls):
    class Bound:
        def __init__(self, addr):
            self.addr = addr

        def emit_transfer(self, value=0):
            RT.transfers.append((self.addr, int(value)))

    return Bound


class _Message:
    @property
    def sender_address(self):
        return RT.sender

    @property
    def value(self):
        return RT.value


gl = types.SimpleNamespace(
    Contract=_Contract,
    public=types.SimpleNamespace(view=_view, write=_Write()),
    evm=types.SimpleNamespace(contract_interface=_contract_interface),
    vm=types.SimpleNamespace(UserError=UserError, Return=Return, run_nondet_unsafe=_run_nondet_unsafe),
    nondet=types.SimpleNamespace(web=_Web(), exec_prompt=_exec_prompt),
    storage=types.SimpleNamespace(copy_to_memory=lambda obj: dataclasses.replace(obj)),
    message=_Message(),
)


def load_contract():
    """(Re)load contracts/deliverable_qa.py against the fake SDK and return the module."""
    fake = types.ModuleType("genlayer")
    for name, obj in dict(gl=gl, allow_storage=allow_storage, TreeMap=TreeMap, DynArray=DynArray,
                          Address=Address, u256=u256, u32=u32).items():
        setattr(fake, name, obj)
    sys.modules["genlayer"] = fake
    spec = importlib.util.spec_from_file_location("deliverable_qa_under_test", CONTRACT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(method, sender, value, *args):
    """Call a contract method as `sender` sending `value`, enforcing payable semantics."""
    kind = getattr(method, "_gl_kind", None)
    if kind is None:
        raise RuntimeError("not a public contract method")
    if int(value) > 0 and kind != "payable":
        raise UserError("non-payable method received value")
    RT.sender = sender
    RT.value = u256(value)
    try:
        return method(*args)
    finally:
        RT.value = u256(0)
