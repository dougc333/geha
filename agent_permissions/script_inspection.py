"""Static checks on scripts a tool call is about to run.

When a command-like argument (`command`, `cmd`, `script`, ...) runs `python|bash|sh|zsh|node
<file>` (or `-c "<code>"` / `-e "<code>"`), the file is read and checked for file deletion,
`rm` through a subprocess, network egress, and reads of secrets (.env, ~/.ssh). Python is
checked on its AST; shell and JavaScript with patterns. Anything that can't be read or
parsed is a finding too (fail closed): an unreadable script is not a safe script.

    findings = inspect_call({"command": "python cleanup.py"}, workdir=".")
    # ["cleanup.py: file deletion (shutil.rmtree)", ...]; empty list means nothing found
"""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

COMMAND_KEYS = ("command", "cmd", "commands", "script", "shell_command", "code_to_run")
MAX_SCRIPT_BYTES = 1_000_000
CONTROL = {"&&", "||", ";", "|", "&", "(", ")", ";;"}
PREFIXES = {"env", "sudo", "nohup", "time", "exec", "nice", "timeout"}
INTERPRETERS = {
    "python": re.compile(r"^python(\d+(\.\d+)?)?$"),
    "shell": re.compile(r"^(ba|z|da|k)?sh$"),
    "node": re.compile(r"^node(js)?$"),
}
SUFFIX_KIND = {".py": "python", ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".js": "node",
               ".mjs": "node", ".cjs": "node"}

NETWORK_MODULES = {"socket", "requests", "urllib", "urllib2", "urllib3", "httpx", "http", "aiohttp", "ftplib",
                   "smtplib", "paramiko", "websocket", "websockets", "telnetlib", "boto3", "botocore"}
DELETE_CALLS = {"remove", "unlink", "rmdir", "removedirs", "rmtree"}
SUBPROCESS_CALLS = {"run", "call", "check_call", "check_output", "Popen", "system", "popen", "spawnl", "spawnv",
                    "execv", "execl", "execvp"}
SECRET = re.compile(r"(^|[/\\~])\.env(\.[\w-]+)?$|(^|[/\\~])\.env\b|\.ssh(/|$)|id_(rsa|ed25519|ecdsa)|\.aws/credentials|\.netrc")
RM = re.compile(r"(^|[\s;&|`(])(rm|rmdir|shred|unlink)\s")

SHELL_CHECKS = [
    ("file deletion", re.compile(r"(^|[\s;&|`(])(rm|rmdir|shred|unlink|truncate)\s|find\b[^\n]*-delete")),
    ("network egress", re.compile(r"(^|[\s;&|`(])(curl|wget|nc|ncat|netcat|scp|sftp|ssh|rsync|ftp|telnet)\s|/dev/tcp/")),
    ("reads secrets", re.compile(r"\.env\b|\.ssh/|~/\.ssh|id_(rsa|ed25519)|\.aws/credentials|\.netrc")),
]
NODE_CHECKS = [
    ("file deletion", re.compile(r"\b(unlink|unlinkSync|rmSync|rmdirSync|rmdir|rm)\s*\(")),
    ("subprocess", re.compile(r"child_process|\bexecSync\b|\bspawn\(|\bexec\(")),
    ("network egress", re.compile(r"require\(\s*['\"](node:)?(https?|net|dgram|tls|http2)['\"]\s*\)|from\s+['\"](node:)?(https?|net|dgram|tls)['\"]"
                                  r"|\bfetch\s*\(|\baxios\b|WebSocket")),
    ("reads secrets", re.compile(r"\.env\b|\.ssh/|id_(rsa|ed25519)|\.aws/credentials|\.netrc")),
]


def _dotted(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def check_python(source: str, label: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as exc:
        return [f"{label}: could not parse Python ({type(exc).__name__}); refusing to run it"]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root in NETWORK_MODULES:
                    found.add(f"network egress (imports {name})")
                if root == "subprocess":
                    found.add("spawns subprocesses (imports subprocess)")
            if isinstance(node, ast.ImportFrom) and node.module in {"os", "shutil", "pathlib"}:
                for alias in node.names:
                    if alias.name in DELETE_CALLS:
                        found.add(f"file deletion (imports {node.module}.{alias.name})")
        elif isinstance(node, ast.Call):
            name = _dotted(node.func)
            last = name.rsplit(".", 1)[-1]
            if last in DELETE_CALLS:
                found.add(f"file deletion ({name or last})")
            if last in SUBPROCESS_CALLS and (name.startswith(("subprocess.", "os.")) or name in SUBPROCESS_CALLS):
                text = " ".join(c.value for c in ast.walk(node) if isinstance(c, ast.Constant) and isinstance(c.value, str))
                if RM.search(" " + text + " ") or re.search(r"(^|\s)rm(\s|$)", text):
                    found.add(f"file deletion through a subprocess ({name})")
            if name in {"__import__", "importlib.import_module"} and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and str(arg.value).split(".")[0] in NETWORK_MODULES:
                    found.add(f"network egress (imports {arg.value})")
                elif not isinstance(arg, ast.Constant):
                    found.add("dynamic import (can't tell what it loads)")
            if name in {"eval", "exec", "compile"}:
                found.add(f"dynamic code ({name})")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and SECRET.search(node.value):
            found.add(f"reads secrets ({node.value[:60]!r})")
    return [f"{label}: {f}" for f in sorted(found)]


def _check_patterns(source: str, label: str, checks) -> list[str]:
    return [f"{label}: {what}" for what, pattern in checks if pattern.search(source)]


def check_source(source: str, kind: str, label: str) -> list[str]:
    if kind == "python":
        return check_python(source, label)
    if kind == "node":
        return _check_patterns(source, label, NODE_CHECKS)
    return _check_patterns(source, label, SHELL_CHECKS)


def _kind(token: str) -> str | None:
    base = Path(token).name
    for kind, pattern in INTERPRETERS.items():
        if pattern.match(base):
            return kind
    return None


def _read(path: Path, label: str) -> tuple[str | None, list[str]]:
    try:
        if path.stat().st_size > MAX_SCRIPT_BYTES:
            return None, [f"{label}: script is larger than {MAX_SCRIPT_BYTES:,} bytes; not inspected, refusing to run it"]
        return path.read_text(encoding="utf-8"), []
    except (OSError, UnicodeDecodeError) as exc:
        return None, [f"{label}: could not read the script ({type(exc).__name__}); refusing to run it"]


def inspect_command(command: str, workdir: str | Path = ".") -> list[str]:
    """Findings for one shell command line (several commands joined by && ; | are all checked)."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError as exc:
        return [f"could not parse the command ({exc}); refusing to run it"]
    findings: list[str] = []
    segment: list[str] = []
    for token in tokens + [";"]:
        if token in CONTROL:
            findings += _inspect_segment(segment, Path(workdir))
            segment = []
        else:
            segment.append(token)
    # A shell one-liner can delete or exfiltrate without any script file.
    findings += [f"command line: {f.split(': ', 1)[1]}" for f in check_source(command, "shell", "x")]
    return list(dict.fromkeys(findings))


def _inspect_segment(tokens: list[str], workdir: Path) -> list[str]:
    while tokens and (tokens[0] in PREFIXES or re.match(r"^\w+=", tokens[0]) or tokens[0].startswith("-")):
        tokens = tokens[1:]
    if not tokens:
        return []
    first = tokens[0]
    kind = _kind(first)
    if kind is None:
        # ./script.py or /path/run.sh executed directly
        suffix_kind = SUFFIX_KIND.get(Path(first).suffix)
        if suffix_kind and ("/" in first):
            return _inspect_file(first, suffix_kind, workdir)
        return []
    rest = tokens[1:]
    while rest:
        token = rest[0]
        if token in {"-c", "-e", "--eval"} and len(rest) > 1:
            return check_source(rest[1], kind, f"inline {Path(first).name} {token}")
        if token == "-m":
            return []  # a module, not a file; the policy rules decide about `python -m ...`
        if token.startswith("-"):
            rest = rest[1:]
            continue
        return _inspect_file(token, kind, workdir)
    return []  # an interactive interpreter with no script


def _inspect_file(name: str, kind: str, workdir: Path) -> list[str]:
    path = Path(name).expanduser()
    if not path.is_absolute():
        path = workdir / path
    source, problems = _read(path, name)
    if source is None:
        return problems
    return check_source(source, SUFFIX_KIND.get(path.suffix, kind), name)


def command_strings(args: dict, keys=COMMAND_KEYS) -> list[str]:
    out = []
    for key in keys:
        value = args.get(key)
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, (list, tuple)):
            if all(isinstance(v, str) for v in value):
                # ["python", "x.py"] argv form, or a list of command lines
                joined = shlex.join(value) if key != "commands" else None
                out += [joined] if joined else list(value)
    return out


def inspect_call(args: dict | None, workdir: str | Path = ".", keys=COMMAND_KEYS) -> list[str]:
    """Findings for every command-like argument of a tool call; [] when none is risky."""
    if not isinstance(args, dict):
        return []
    findings: list[str] = []
    for command in command_strings(args, keys):
        findings += inspect_command(command, workdir)
    return findings
