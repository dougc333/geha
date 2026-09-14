"""Allowlisted, isolated runner for trusted local simulation scripts.

Not a security sandbox for untrusted Python. Tool callers cannot supply code,
commands, environment variables, or filesystem paths.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import signal
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Flow:
    folder: str
    script: str
    records: str
    events: str
    dependencies: tuple[str, ...] = ()


FLOWS = {
    "01": Flow(
        "01_membership_benefits",
        "simulate_membership.py",
        "members.json",
        "membership_events.json",
    ),
    "02": Flow(
        "02_provider_operations",
        "simulate_providers.py",
        "providers.json",
        "provider_events.json",
    ),
    "03": Flow(
        "03_utilization_management",
        "simulate_utilization.py",
        "authorizations.json",
        "um_events.json",
    ),
    "04": Flow(
        "04_premium_billing",
        "simulate_premium_billing.py",
        "premium_ledger.json",
        "billing_events.json",
        ("01",),
    ),
    "05": Flow(
        "05_appeals_disputes",
        "simulate_appeals.py",
        "appeals.json",
        "appeals_events.json",
    ),
    "06": Flow(
        "06_payment_integrity",
        "simulate_payment_integrity.py",
        "screening_log.json",
        "integrity_events.json",
    ),
    "07": Flow(
        "07_care_case_management",
        "simulate_care_management.py",
        "care_cases.json",
        "care_events.json",
    ),
    "08": Flow(
        "08_member_services",
        "simulate_member_services.py",
        "inquiries.json",
        "service_events.json",
        ("01", "03"),
    ),
    "09": Flow(
        "09_compliance",
        "simulate_compliance.py",
        "compliance_register.json",
        "compliance_events.json",
        tuple(f"{i:02}" for i in range(1, 9)),
    ),
}
MAX_JSON = 2 * 1024 * 1024
MAX_LOG = 256 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    if path.is_symlink() or path.stat().st_size > MAX_JSON:
        raise ValueError("Unsafe or oversized JSON file")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


class FlowService:
    def __init__(self, root: Path, runs: Path, claims: Path, timeout=30, max_runs=100):
        self.root, self.runs, self.claims = (
            root.resolve(),
            runs.resolve(),
            claims.resolve(),
        )
        self.timeout, self.max_runs = timeout, max_runs
        self.slots = asyncio.Semaphore(2)

    def flow(self, flow_id):
        if flow_id not in FLOWS:
            raise ValueError("flow_id must be one of 01 through 09")
        return FLOWS[flow_id]

    def list_flows(self):
        return {
            "simulation_only": True,
            "flows": [
                {
                    "flow_id": key,
                    "name": f.folder,
                    "dependencies": list(f.dependencies),
                    "outputs": ["mcp_response.json", f.records, f.events],
                }
                for key, f in FLOWS.items()
            ],
        }

    def plan(self, requested):
        needed = set()

        def visit(key):
            for dep in self.flow(key).dependencies:
                visit(dep)
            needed.add(key)

        for key in requested:
            visit(key)
        return sorted(needed)

    async def execute(self, requested):
        plan = self.plan(requested)  # Validate before creating files.
        if self.slots.locked():
            raise RuntimeError("Server busy: two runs are already active; retry later")
        async with self.slots:
            self.runs.mkdir(parents=True, exist_ok=True)
            if sum(p.is_dir() for p in self.runs.glob("run_*")) >= self.max_runs:
                raise RuntimeError(
                    "Run quota reached; archive old run folders before retrying"
                )
            run_id = "run_" + uuid.uuid4().hex
            work = self.runs / run_id
            work.mkdir(mode=0o700)
            manifest = {
                "run_id": run_id,
                "status": "running",
                "started_at": now(),
                "requested": requested,
                "execution_order": plan,
                "completed_flows": [],
                "warnings": [],
                "script_sha256": {},
                "simulation_only": True,
            }
            write_json(work / "run.json", manifest)
            try:
                # Copy only allowlisted scripts: never copy stale outputs/templates.
                for key in plan:
                    f = self.flow(key)
                    original = self.root / f.folder / f.script
                    if original.is_symlink() or not original.resolve().is_relative_to(
                        self.root
                    ):
                        raise ValueError("Simulator source escapes project root")
                    content = original.read_bytes()
                    dest = work / f.folder
                    dest.mkdir()
                    (dest / f.script).write_bytes(content)
                    manifest["script_sha256"][key] = hashlib.sha256(content).hexdigest()
                claims_dest = work / "claims" / "audit_trails.json"
                if any(key in plan for key in ("08", "09")):
                    if self.claims.exists():
                        claims = read_json(self.claims)
                        if not isinstance(claims, list) or any(
                            not isinstance(r, dict)
                            or not isinstance(r.get("claim_id"), str)
                            or not isinstance(r.get("final_status"), str)
                            for r in claims
                        ):
                            raise ValueError(
                                "Claims audit input must be a list of claim/status records"
                            )
                        claims_dest.parent.mkdir()
                        write_json(claims_dest, claims)
                        manifest["claims_snapshot"] = {
                            "source": str(self.claims),
                            "records": len(claims),
                            "sha256": hashlib.sha256(
                                claims_dest.read_bytes()
                            ).hexdigest(),
                            "note": "Existing audit data snapshot; claims adjudication was not rerun.",
                        }
                    else:
                        manifest["warnings"].append(
                            "Claims audit input is missing; lookups may return NOT_FOUND and compliance evidence will be incomplete."
                        )
                for key in plan:
                    await self._run_script(work, key, claims_dest)
                    f = self.flow(key)
                    folder = work / f.folder
                    payload = read_json(folder / "mcp_response.json")
                    if (
                        not isinstance(payload, dict)
                        or payload.get("flow") != f.folder
                        or payload.get("example_only") is not False
                        or payload.get("simulation_only") is not True
                        or payload.get("execution_status") != "completed"
                        or not isinstance(payload.get("summary"), dict)
                        or payload.get("outputs") != [f.records, f.events]
                    ):
                        raise ValueError("Missing or invalid simulator response")
                    for output in (f.records, f.events):
                        if not isinstance(read_json(folder / output), list):
                            raise ValueError("Invalid simulator output records")
                    payload["run_id"] = run_id
                    payload["generated_at"] = now()
                    write_json(folder / "mcp_response.json", payload)
                    manifest["completed_flows"].append(key)
                    write_json(work / "run.json", manifest)
                manifest["status"] = "completed"
                manifest["finished_at"] = now()
                write_json(work / "run.json", manifest)
                return {
                    "run_id": run_id,
                    "execution_status": "completed",
                    "simulation_only": True,
                    "execution_order": plan,
                    "warnings": manifest["warnings"],
                    "results": {
                        k: read_json(work / FLOWS[k].folder / "mcp_response.json")
                        for k in requested
                    },
                }
            except BaseException as exc:
                manifest["status"] = (
                    "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
                )
                manifest["finished_at"] = now()
                message = (
                    "Simulator exceeded its execution timeout"
                    if isinstance(exc, TimeoutError)
                    else str(exc)
                )
                manifest["error"] = message[:1000]
                write_json(work / "run.json", manifest)
                if isinstance(exc, asyncio.CancelledError):
                    raise
                raise RuntimeError(f"Run {run_id} failed: {message}") from exc

    async def _run_script(self, work, key, claims_dest):
        f = self.flow(key)
        folder = work / f.folder
        # No shell; no inherited API keys or user-controlled environment.
        env = {
            "PATH": os.defpath,
            "PYTHONIOENCODING": "utf-8",
            "GEHA_CLAIMS_PATH": str(claims_dest),
        }
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-B",
            str(folder / f.script),
            cwd=folder,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )

        async def drain(stream):
            chunks, size = [], 0
            while chunk := await stream.read(8192):
                size += len(chunk)
                if size > MAX_LOG:
                    raise RuntimeError("Simulator exceeded log size limit")
                chunks.append(chunk)
            return b"".join(chunks)

        async def collect():
            stdout, stderr = await asyncio.gather(
                drain(proc.stdout), drain(proc.stderr)
            )
            await proc.wait()
            return stdout, stderr

        task = asyncio.create_task(collect())
        try:
            stdout, stderr = await asyncio.wait_for(task, self.timeout)
            (folder / "stdout.log").write_bytes(stdout)
            (folder / "stderr.log").write_bytes(stderr)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Flow {key} exited with status {proc.returncode}; see isolated stderr.log"
                )
        except BaseException:
            # Kill process group on timeout/cancellation, not just the parent.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await proc.wait()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise

    def manifest(self, run_id):
        if not re.fullmatch(r"run_[a-f0-9]{32}", run_id):
            raise ValueError("Invalid run_id")
        folder = self.runs / run_id
        if folder.is_symlink() or not folder.resolve().is_relative_to(self.runs):
            raise ValueError("Invalid run directory")
        if not (folder / "run.json").is_file():
            raise ValueError("Unknown run_id")
        return folder, read_json(folder / "run.json")

    def result(self, flow_id, run_id):
        f = self.flow(flow_id)
        folder, m = self.manifest(run_id)
        if m["status"] != "completed" or flow_id not in m["completed_flows"]:
            raise ValueError("No completed result for this flow and run")
        if (folder / f.folder).is_symlink():
            raise ValueError("Invalid flow directory")
        return read_json(folder / f.folder / "mcp_response.json")

    def records(self, flow_id, run_id, kind, offset=0, limit=50):
        self.result(flow_id, run_id)
        if kind not in ("records", "events") or offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Use records/events, offset >= 0, and limit 1..100")
        f = self.flow(flow_id)
        data = read_json(self.runs / run_id / f.folder / getattr(f, kind))
        return {
            "run_id": run_id,
            "flow_id": flow_id,
            "total": len(data),
            "offset": offset,
            "items": data[offset : offset + limit],
            "next_offset": offset + limit if offset + limit < len(data) else None,
        }
