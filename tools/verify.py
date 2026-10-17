"""Independent differential acceptance: reference and candidate run separately."""

import argparse
import ast
import hashlib
import itertools
import json
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESTRICT = [
    "--rm",
    "--network",
    "none",
    "--read-only",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "32",
    "--memory",
    "128m",
    "--cpus",
    "1",
    "--user",
    "65534:65534",
    "-i",
]
RUNNER = """import json,sys,types,copy
ns={}
exec(compile(sys.argv[1],"engine.py","exec"),ns)
results=[]
for item in json.load(sys.stdin):
 before=copy.deepcopy(item)
 try:
  result=ns['slide'](item['row']) if item['kind']=='slide' else ns['move'](item['board'],item['direction'])
  results.append({'value':result,'unchanged':before==item})
 except ValueError:
  results.append({'error':'ValueError','unchanged':before==item})
 except Exception as exc:
  results.append({'error':type(exc).__name__,'unchanged':before==item})
print(json.dumps(results))
"""


def admission(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            n.name not in {"math", "typing", "collections"} for n in node.names
        ):
            raise ValueError("Unapproved candidate import")
        if isinstance(node, ast.ImportFrom) and node.module not in {
            "math",
            "typing",
            "collections",
        }:
            raise ValueError("Unapproved candidate import")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Candidate object internals are not permitted")
        if isinstance(node, ast.Name) and node.id in {
            "eval",
            "exec",
            "compile",
            "open",
            "input",
            "__import__",
            "globals",
            "locals",
            "getattr",
            "setattr",
            "delattr",
            "vars",
        }:
            raise ValueError("Candidate dynamic execution or I/O is not permitted")


def bounded(args, payload):
    result = subprocess.run(
        args,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=40,
        check=True,
    )
    return json.loads(result.stdout)


def cases(seed, exhaustive):
    rng = random.Random(seed)
    items = []
    if exhaustive:
        items += [
            {"kind": "slide", "row": list(row)}
            for row in itertools.product([0, 2, 4, 8, 16, 32, 64], repeat=4)
        ]
    else:
        items += [
            {
                "kind": "slide",
                "row": [
                    rng.choice([0] + [2**i for i in range(1, 21)]) for _ in range(4)
                ],
            }
            for _ in range(2401)
        ]
    for _ in range(500):
        board = [
            [rng.choice([0] + [2**i for i in range(1, 21)]) for _ in range(4)]
            for _ in range(4)
        ]
        items += [
            {"kind": "move", "board": board, "direction": direction}
            for direction in ["left", "right", "up", "down"]
        ]
    items += [
        {"kind": "slide", "row": row}
        for row in [[2, 2, 4, 0], [2, 2, 2, 2], [4, 0, 4, 4], [0] * 4, [2**20] * 4]
    ]
    return items


def invalid_cases():
    rows = [
        None,
        [],
        [0] * 3,
        [0] * 5,
        [True, 0, 0, 0],
        [2.0, 0, 0, 0],
        [-2, 0, 0, 0],
        [3, 0, 0, 0],
        [1, 0, 0, 0],
        [2**21, 0, 0, 0],
        ["2", 0, 0, 0],
        {"x": 1},
    ]
    items = [{"kind": "slide", "row": row} for row in rows]
    items += [
        {"kind": "move", "board": b, "direction": "left"}
        for b in [
            None,
            [],
            [[0] * 4] * 3,
            [[0] * 3] * 4,
            [[0] * 4, [0] * 4, [0] * 4, [True, 0, 0, 0]],
        ]
    ]
    items += [
        {"kind": "move", "board": [[0] * 4 for _ in range(4)], "direction": d}
        for d in ["LEFT", "diagonal", None, 0]
    ]
    return items


def verify(seed, exhaustive=True, native_library=None, source_override=None):
    source = (
        source_override
        if source_override is not None
        else (ROOT / "engine.py").read_text()
    )
    admission(source)
    valid = cases(seed, exhaustive)
    if native_library:
        import os

        env = dict(
            os.environ, AYA_REFERENCE_LIBRARY=str(Path(native_library).resolve())
        )
        r = subprocess.run(
            ["python3", str(ROOT / "tools/oracle.py")],
            input=json.dumps(valid),
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
            env=env,
        )
        expected = json.loads(r.stdout)
    else:
        expected = bounded(
            [
                "docker",
                "run",
                *RESTRICT,
                "-v",
                str(ROOT / "reference") + ":/reference:ro",
                "-v",
                str(ROOT / "tools/oracle.py") + ":/oracle.py:ro",
                "python:3.12-slim",
                "python",
                "-B",
                "/oracle.py",
            ],
            valid,
        )
    invalid = invalid_cases()
    actual = bounded(
        [
            "docker",
            "run",
            *RESTRICT,
            "python:3.12-slim",
            "python",
            "-B",
            "-c",
            RUNNER,
            source,
        ],
        valid + invalid,
    )
    failures = []
    for i, (item, want, got) in enumerate(zip(valid, expected, actual)):
        if got.get("value") != want or not got["unchanged"]:
            failures.append(
                {"index": i, "input": item, "expected": want, "actual": got}
            )
    for i, (item, got) in enumerate(zip(invalid, actual[len(valid) :])):
        if got.get("error") != "ValueError" or not got["unchanged"]:
            failures.append(
                {
                    "index": len(valid) + i,
                    "input": item,
                    "expected": "ValueError without mutation",
                    "actual": got,
                }
            )
    total = len(valid) + len(invalid)
    return {
        "seed": seed,
        "exhaustive_rows": exhaustive,
        "total": total,
        "passed": total - len(failures),
        "native_comparisons": len(valid),
        "contract_negative_checks": len(invalid),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "failures": failures,
        "isolation": {
            "candidate": "network-none read-only Docker; no mounts; no native reference",
            "reference": "separate process; unchanged native functions",
        },
        "examples": [
            {"input": valid[i], "expected": expected[i], "actual": actual[i]["value"]}
            for i in range(len(valid) - 5, len(valid))
        ],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=20482026)
    p.add_argument("--holdout", action="store_true")
    p.add_argument("--native-library")
    p.add_argument("--output", default="evidence/verification.json")
    args = p.parse_args()
    report = verify(args.seed, not args.holdout, args.native_library)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "total": report["total"],
                "source_sha256": report["source_sha256"],
            }
        )
    )
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
