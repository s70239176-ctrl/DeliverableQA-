#!/usr/bin/env python3
"""Static invariant checks for contracts/deliverable_qa.py. No GenVM, no network, stdlib only.

    python scripts/preflight.py [path/to/contract.py]

Exit code 0 = every invariant holds. These mirror the Studio failure modes in docs/STUDIO_TEST_PLAN.md.
"""
import ast
import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "contracts" / "deliverable_qa.py"
# Hash published in the GenLayer docs / boilerplate. If Studio's boilerplate differs, update this constant.
DOCS_DEPENDS_HASH = "1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"
ALLOWED_SIMPLE = {"str", "bool", "Address", "u256", "u32"}
FORBIDDEN_FIELD_TYPES = {"list", "dict", "int", "set", "float", "List", "Dict"}
PAYABLE_ALLOWED = {"open_escrow"}
NONDET_ONLY_IN = {"_make_evaluator"}
SELF_FREE_FUNCS = {"_make_evaluator", "_make_validator"}

failures = []
passes = []


def ok(name):
    passes.append(name)
    print("PASS  " + name)


def bad(name, detail=""):
    failures.append(name)
    print("FAIL  " + name + (" -> " + detail if detail else ""))


def check(cond, name, detail=""):
    ok(name) if cond else bad(name, detail)


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def ann_name(node):
    if node is None:
        return None
    if isinstance(node, ast.Constant) and node.value is None:
        return "None"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return ann_name(node.value)
    return dotted(node) or ast.dump(node)


def main(path):
    src = Path(path).read_text()
    lines = src.splitlines()
    tree = ast.parse(src)

    # 1. Magic comment
    m = re.fullmatch(r'# \{ "Depends": "py-genlayer:([0-9a-z]+)" \}', lines[0].strip()) if lines else None
    check(m is not None, "line 1 is the GenLayer Depends magic comment", lines[0] if lines else "empty file")
    if m:
        h = m.group(1)
        check(len(h) == 52, "Depends hash has the expected 52 characters", "got %d (extra/missing character?)" % len(h))
        check(h == DOCS_DEPENDS_HASH, "Depends hash equals the docs/boilerplate hash",
              "got %s; if Studio's boilerplate shows this one, update DOCS_DEPENDS_HASH" % h)

    # 2. Imports
    check(any(isinstance(n, ast.ImportFrom) and n.module == "genlayer" and any(a.name == "*" for a in n.names)
              for n in tree.body), "from genlayer import * present")

    # 3. Exactly one gl.Contract, named DeliverableQA
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    contracts = [c for c in classes if any(dotted(b) == "gl.Contract" for b in c.bases)]
    check(len(contracts) == 1 and contracts[0].name == "DeliverableQA", "exactly one gl.Contract, named DeliverableQA")
    if len(contracts) != 1:
        return
    cls = contracts[0]

    # 4. Storage field declarations
    fields = {}
    for n in cls.body:
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            fields[n.target.id] = n.annotation
    check(bool(fields), "persistent fields declared on the class body", "none found")
    for name, a in fields.items():
        base = ann_name(a)
        specialized = not (base in ("TreeMap", "DynArray") and not isinstance(a, ast.Subscript))
        check(base not in FORBIDDEN_FIELD_TYPES, "field '%s' avoids forbidden type %s" % (name, base))
        check(specialized, "field '%s' is fully specialized" % name, "bare %s" % base)

    # 5. every self.X = ... assignment targets a declared field
    undeclared = set()
    for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for t in targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                    if t.attr not in fields:
                        undeclared.add(t.attr)
    check(not undeclared, "no self.<field> assignment to an undeclared field", str(sorted(undeclared)))

    # 6. Storage dataclasses: @allow_storage + @dataclass, no forbidden field types, sized ints
    for c in classes:
        decos = {dotted(d) for d in c.decorator_list}
        if "allow_storage" in decos:
            check("dataclass" in decos, "%s has @dataclass beside @allow_storage" % c.name)
            for n in c.body:
                if isinstance(n, ast.AnnAssign):
                    check(ann_name(n.annotation) not in FORBIDDEN_FIELD_TYPES,
                          "%s.%s avoids forbidden type" % (c.name, n.target.id))

    # 7. Constructor + public method rules
    init = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
    check(init is not None and not init.decorator_list, "__init__ exists and has no decorators")
    public = {}
    for n in cls.body:
        if isinstance(n, ast.FunctionDef):
            kinds = [dotted(d) for d in n.decorator_list if dotted(d).startswith("gl.public")]
            if kinds:
                public[n.name] = (n, kinds[0])
    check({"open_escrow", "deliver", "review", "cancel", "withdraw", "get_job", "get_credit", "get_status"} <= set(public),
          "all 8 required public methods exist")
    for name, (fn, kind) in public.items():
        args = [a for a in fn.args.args if a.arg != "self"]
        check(all(a.annotation is not None for a in args), "%s: every argument annotated" % name)
        check(fn.returns is not None, "%s: return annotated" % name)
        types_ok = all(ann_name(a.annotation) in ALLOWED_SIMPLE for a in args) and ann_name(fn.returns) in ALLOWED_SIMPLE | {"None"}
        check(types_ok, "%s: only Studio-renderable simple types (str/bool/Address/u256/u32/None)" % name)
        is_payable = kind == "gl.public.write.payable"
        check(is_payable == (name in PAYABLE_ALLOWED), "%s: payable decorator only where value is expected" % name, kind)
        if name.startswith("get_"):
            check(kind == "gl.public.view", "%s is a view" % name)

    # 8. Nondet rules
    outside = []
    for top in tree.body:
        scope = top.name if isinstance(top, (ast.FunctionDef, ast.ClassDef)) else "<module>"
        for node in ast.walk(top):
            if isinstance(node, ast.Attribute) and dotted(node).startswith("gl.nondet") and scope not in NONDET_ONLY_IN:
                outside.append("%s in %s" % (dotted(node), scope))
    check(not outside, "gl.nondet.* appears only inside %s" % sorted(NONDET_ONLY_IN), "; ".join(sorted(set(outside))))
    for top in tree.body:
        if isinstance(top, ast.FunctionDef) and top.name in SELF_FREE_FUNCS:
            uses_self = any(isinstance(n, ast.Name) and n.id == "self" for n in ast.walk(top))
            check(not uses_self, "%s never touches self (storage is inaccessible in nondet)" % top.name)
    all_names = {dotted(n) for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    check(not any("strict_eq" in n for n in all_names), "no strict_eq call anywhere")
    check("gl.vm.run_nondet_unsafe" in all_names, "uses gl.vm.run_nondet_unsafe(leader, validator)")
    check("gl.storage.copy_to_memory" in all_names, "uses gl.storage.copy_to_memory before the nondet call")
    check(not any(n.endswith("get_contract_at") for n in all_names), "no gl.get_contract_at")
    emitters = []
    for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and node.attr in ("emit", "emit_transfer"):
                emitters.append(fn.name)
    check(set(emitters) == {"withdraw"}, "value transfers happen only in withdraw()", str(sorted(set(emitters))))
    review = public.get("review", (None,))[0]
    if review is not None:
        seq = [(n.lineno, dotted(n)) for n in ast.walk(review) if isinstance(n, ast.Attribute)]
        line = lambda name: min((ln for ln, d in seq if d.endswith(name)), default=None)
        c2m, run = line("copy_to_memory"), line("run_nondet_unsafe")
        check(c2m is not None and run is not None and c2m < run, "review(): copy_to_memory happens before run_nondet_unsafe")
        writes_after = [n.lineno for n in ast.walk(review) if isinstance(n, ast.Assign)
                        for t in n.targets if isinstance(t, ast.Attribute) and dotted(t).startswith("job.")]
        check(bool(writes_after) and run is not None and min(writes_after) > run, "review(): storage writes only after the nondet call returns")
    check("import json" in src and "import typing" in src, "json and typing imported")
    check("localStorage" not in src and "api_key" not in src.lower(), "no API keys / browser storage")

    print("\n%d passed, %d failed" % (len(passes), len(failures)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    sys.exit(1 if failures else 0)
