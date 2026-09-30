#!/usr/bin/env python3
"""Tools the agent's reflector wrote for it, held for approval before the agent can use them.

    python learned.py list
    python learned.py show <name>
    python learned.py approve <name>     # a person has read the code: the agent may use it
    python learned.py reject <name>

A learned tool is one Python function over the same claims table the built-in analytics
tools use:

    def name(rows, names, deaths, <parameters with defaults>) -> str

  rows    one dict per claim: eob, patient, provider, facility, date, start, minutes, code,
          service, lines, paid
  names   {"Practitioner/<id>": "Dr. ..."}
  deaths  {"Patient/<id>": "YYYY-MM-DD"}

improve.py --tools asks the reflector for one when a graded run missed a scheme that no
existing tool covers. The code is checked (validate), run in a separate process with no
file or network builtins and a time limit (run), tested against the miss it was written
for, and saved as **pending**. Only approved tools are loaded by agent.py.

This is a basic guard, not a security boundary: read the code before approving it.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIR = HERE / "learned_tools"
REGISTRY = DIR / "registry.json"
ALLOWED_IMPORTS = {"collections", "statistics", "datetime", "json", "math", "itertools", "re"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "getattr",
                   "setattr", "delattr", "input", "breakpoint", "exit", "quit", "help", "memoryview"}
PARAM_TYPES = {"int": int, "float": float, "str": str, "bool": bool}
MAX_OUTPUT = 200_000
TIMEOUT_S = 20

# Runs in a child process: exec the function with a short list of builtins and call it.
RUNNER = r"""
import builtins, json, resource, sys
resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
job = json.load(sys.stdin)
ALLOWED = set(job["allowed_imports"])
real_import = builtins.__import__
def limited_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in ALLOWED:
        raise ImportError(f"import of {name} is not allowed in a learned tool")
    return real_import(name, globals, locals, fromlist, level)
SAFE = ["abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "frozenset", "int", "isinstance",
        "len", "list", "map", "max", "min", "range", "repr", "reversed", "round", "set", "sorted", "str", "sum", "tuple",
        "zip", "ValueError", "KeyError", "TypeError", "IndexError", "ZeroDivisionError", "Exception"]
env = {"__builtins__": {**{n: getattr(builtins, n) for n in SAFE}, "__import__": limited_import}}
exec(compile(job["code"], "<learned tool>", "exec"), env)
result = env[job["name"]](job["rows"], job["names"], job["deaths"], **job["kwargs"])
sys.stdout.write(result if isinstance(result, str) else json.dumps(result, default=str))
"""


class Rejected(ValueError):
    """The generated code breaks the contract for a learned tool."""


def validate(code: str) -> dict:
    """Checks the code is one plain function over (rows, names, deaths, ...). Returns its
    name, description and parameters ({name: (type, default)})."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise Rejected(f"syntax error: {exc}") from exc
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(m.split(".")[0] not in ALLOWED_IMPORTS for m in modules):
                raise Rejected(f"import not allowed: {modules} (allowed: {sorted(ALLOWED_IMPORTS)})")
        elif not isinstance(node, ast.FunctionDef):
            raise Rejected("only imports and one function are allowed at the top level")
    if len(functions) != 1:
        raise Rejected("exactly one top-level function is required")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in tree.body:
            raise Rejected("imports must be at the top of the file")
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id.startswith("__")):
            raise Rejected(f"name not allowed: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise Rejected(f"attribute not allowed: {node.attr}")
        if isinstance(node, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.ClassDef, ast.With, ast.Try, ast.While)):
            raise Rejected(f"{type(node).__name__} is not allowed")
    fn = functions[0]
    args = fn.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
        raise Rejected("only plain parameters are allowed")
    if [a.arg for a in args.args[:3]] != ["rows", "names", "deaths"]:
        raise Rejected("the first three parameters must be rows, names, deaths")
    extra = args.args[3:]
    if len(args.defaults) != len(extra):
        raise Rejected("every parameter after rows, names, deaths needs a default")
    params = {}
    for arg, default in zip(extra, args.defaults):
        kind = getattr(arg.annotation, "id", None)
        if kind not in PARAM_TYPES or not isinstance(default, ast.Constant) or not isinstance(default.value, PARAM_TYPES[kind]):
            raise Rejected(f"parameter {arg.arg} must be annotated int, float, str or bool with a matching constant default")
        params[arg.arg] = (kind, default.value)
    description = ast.get_docstring(fn)
    if not description or fn.name.startswith("_") or not fn.name.isidentifier():
        raise Rejected("the function needs a public name and a docstring (it becomes the tool description)")
    return {"name": fn.name, "description": description, "params": params}


def run(code: str, name: str, rows: list[dict], names: dict, deaths: dict, kwargs: dict | None = None) -> str:
    """Runs the function in a child process (isolated interpreter, empty environment, temp
    directory, CPU and wall-clock limits). Raises RuntimeError with the child's error."""
    job = {"code": code, "name": name, "rows": rows, "names": names, "deaths": deaths, "kwargs": kwargs or {},
           "allowed_imports": sorted(ALLOWED_IMPORTS)}
    with tempfile.TemporaryDirectory() as cwd:
        try:
            done = subprocess.run([sys.executable, "-I", "-c", RUNNER], input=json.dumps(job), capture_output=True,
                                  text=True, timeout=TIMEOUT_S, cwd=cwd, env={})
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"learned tool {name} ran longer than {TIMEOUT_S}s") from exc
    if done.returncode != 0:
        raise RuntimeError(f"learned tool {name} failed: {done.stderr.strip().splitlines()[-1] if done.stderr.strip() else 'no output'}")
    return done.stdout[:MAX_OUTPUT]


def registry() -> dict:
    return json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}


def save(code: str, spec: dict, written_for: str, check: dict, status: str = "pending") -> None:
    DIR.mkdir(exist_ok=True)
    (DIR / f"{spec['name']}.py").write_text(code.rstrip() + "\n")
    entries = registry()
    entries[spec["name"]] = {"status": status, "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "description": spec["description"], "params": spec["params"], "written_for": written_for,
                             "check": check}
    REGISTRY.write_text(json.dumps(entries, indent=1) + "\n")


def set_status(name: str, status: str) -> None:
    entries = registry()
    if name not in entries:
        sys.exit(f"no learned tool named {name}")
    entries[name]["status"] = status
    REGISTRY.write_text(json.dumps(entries, indent=1) + "\n")


def langchain_tools(statuses: tuple[str, ...] = ("approved",)) -> list:
    """The learned tools with one of these statuses, as tools the agent can call."""
    from langchain_core.tools import StructuredTool
    from pydantic import create_model

    import tools as analytics

    out = []
    for name, entry in registry().items():
        if entry["status"] not in statuses:
            continue
        code = (DIR / f"{name}.py").read_text()
        spec = validate(code)  # the file may have been edited since it was saved
        schema = create_model(f"{name}_args", **{p: (PARAM_TYPES[kind], default) for p, (kind, default) in spec["params"].items()})

        def call(_code=code, _name=name, **kwargs) -> str:
            rows, names, deaths = analytics.claims()
            try:
                return run(_code, _name, rows, names, deaths, kwargs)
            except RuntimeError as exc:
                return f"[TOOL ERROR: {exc}]"

        out.append(StructuredTool.from_function(func=call, name=name, args_schema=schema,
                                                description=spec["description"] + "\n(Learned tool: written after an earlier graded investigation.)"))
    return out


def main() -> None:
    command, name = (sys.argv[1:] + ["", ""])[:2]
    entries = registry()
    if command == "list":
        for tool, e in entries.items():
            passed = "passed" if e["check"].get("passed") else "FAILED"
            print(f"{e['status']:9} {tool}  (check {passed}; written for: {e['written_for'][:70]})")
        if not entries:
            print("no learned tools yet")
    elif command == "show" and name in entries:
        print(json.dumps(entries[name], indent=1))
        print((DIR / f"{name}.py").read_text())
    elif command in ("approve", "reject") and name:
        set_status(name, "approved" if command == "approve" else "rejected")
        print(f"{name}: {'approved' if command == 'approve' else 'rejected'}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
