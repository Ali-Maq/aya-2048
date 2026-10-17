"""Rerun native recovery using the installed AYA factory and dedicated worker.

The worker slot and REA document are shared. Run only while the factory is idle.
The script never substitutes recorded evidence for native calls.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory", type=Path, default=ROOT.parent / "onyx/aya")
    args = parser.parse_args()
    sys.path.insert(0, str(args.factory.resolve()))
    from aya_factory import agents
    from aya_factory.core import Journal, run, save
    from aya_factory.rea import ReaClient

    sys.path.insert(0, str(ROOT / "tools"))
    import verify

    spec = json.loads((ROOT / "specs/tile-movement.json").read_text())
    provenance = spec["reference"]
    for name, digest in provenance["sha256"].items():
        if (
            hashlib.sha256((ROOT / "reference" / name).read_bytes()).hexdigest()
            != digest
        ):
            raise RuntimeError("Reference digest changed: " + name)
    reference = args.factory / ".state/reference/game-2048"
    reference.mkdir(parents=True, exist_ok=True)
    for name in ["2048-linux-aarch64", "lib2048-linux-aarch64.so"]:
        shutil.copy2(ROOT / "reference" / name, reference / name)
    shutil.copy2(ROOT / "tools/reference_probe.py", reference / "probe.py")
    run_id = "game-2048-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    directory = ROOT / ".work" / run_id
    journal = Journal(directory)
    snapshot = json.loads(run(["gh", "api", "repos/Ali-Maq/aya-2048/issues/1"]))
    journal.emit(
        "request_frozen",
        issue=snapshot["html_url"],
        updated_at=snapshot["updated_at"],
        target="Ali-Maq/aya-2048",
        contract_sha256=hashlib.sha256(
            (ROOT / "specs/tile-movement.json").read_bytes()
        ).hexdigest(),
    )
    plan = agents.plan(spec, directory, journal)
    prompt = (
        """Read reverse-engineer-anything and test-driven-development skills. Recover the bounded 2048 movement mechanic from a compiled binary. Do not read/fetch original C source. REA server binary /reference/game-2048/2048-linux-aarch64. Call REA open_binary(provider_id=ghidra), procedure_pseudo_code for slideArray and findTarget (other movement procedures as needed), then capture_process_scenario executable=/usr/local/bin/python3 arguments=["-B","/reference/game-2048/probe.py"] working_directory=/tmp timeout_ms=10000 limits={"output_bytes":30000}. Keep canonical evidence IDs. Write engine.py with slide(row) and move(board,direction) plus tests/test_agent_engine.py. Pure Python; no file I/O, subprocess, native libs, network, dynamic execution. Imports only math,typing,collections. Use one delegate_task review; child must not delegate. Write and run real red/green unit tests. Return JSON {summary:string,tests_run:string,evidence_ids:[strings],observations:[strings],limitations:[strings]}. Contract:\n"""
        + json.dumps(spec)
        + "\nPlan:\n"
        + json.dumps(plan)
    )
    result = agents.worker(prompt, directory, journal, "recovery")
    candidate = run(
        [
            "nemohermes",
            "aya-feature",
            "exec",
            "--timeout",
            "20",
            "--no-stdin",
            "--",
            "cat",
            "/sandbox/aya/" + run_id + "/engine.py",
        ],
        timeout=45,
    )
    tests = run(
        [
            "nemohermes",
            "aya-feature",
            "exec",
            "--timeout",
            "20",
            "--no-stdin",
            "--",
            "cat",
            "/sandbox/aya/" + run_id + "/tests/test_agent_engine.py",
        ],
        timeout=45,
    )
    report = verify.verify(
        int.from_bytes(os.urandom(8), "big"), source_override=candidate
    )
    holdout = verify.verify(
        int.from_bytes(os.urandom(8), "big"), False, source_override=candidate
    )
    save(directory / "verification.json", report)
    save(directory / "holdout.json", holdout)
    if any(r["passed"] != r["total"] for r in [report, holdout]):
        raise RuntimeError(
            "Acceptance failed; candidate retained without replacing deployed engine"
        )
    bundle = ReaClient().call("get_evidence_bundle", {"detail": "complete"})
    ids = set(result["evidence_ids"])
    records = [
        r
        for r in bundle.get("result", {}).get("records", [])
        if r.get("evidence_id") in ids
    ]
    if not any(
        r.get("operation") == "procedure_pseudo_code" for r in records
    ) or not any(r.get("operation") == "capture_process_scenario" for r in records):
        raise RuntimeError("Native REA evidence missing")
    save(directory / "rea-evidence.json", {"claimed": sorted(ids), "records": records})
    (ROOT / "engine.py").write_text(candidate)
    (ROOT / "tests/test_agent_engine.py").write_text(tests)
    save(ROOT / "evidence/verification.json", report)
    save(ROOT / "evidence/holdout.json", holdout)
    public = ROOT / "evidence" / run_id
    public.mkdir()
    for name in [
        "crusoe.json",
        "recovery-audit.json",
        "recovery-result.json",
        "rea-evidence.json",
        "trace.json",
        "events.jsonl",
        "verification.json",
        "holdout.json",
    ]:
        if (directory / name).exists():
            shutil.copy2(directory / name, public / name)
    journal.emit(
        "acceptance_passed",
        source_sha256=report["source_sha256"],
        checks=report["total"] + holdout["total"],
    )
    print(
        "Verified candidate ready for Git review. No branch, PR, or deployment is fabricated."
    )
    print(public)


if __name__ == "__main__":
    main()
