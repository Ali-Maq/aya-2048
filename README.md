# AYA 2048

A bounded game mechanic recovered from an actual native binary and integrated into a playable browser game.

[Feature request](https://github.com/Ali-Maq/aya-2048/issues/1) · [Contract](specs/tile-movement.json) · [Reference provenance](evidence/provenance.json)

The reference is the MIT-licensed [mevdschee/2048.c](https://github.com/mevdschee/2048.c), pinned at `90343eb209e84fa9687d596f5d5eecfdf7d4df51`. Its unchanged C source was compiled into a Linux ARM64 ELF executable and shared library. Hermes receives the executable path, a behavior contract, and REA tools; it is not supplied the C source. The source is retained here for reproducible builds and independent verification.

## Run the game

Python 3.12 and Docker are required. Start from this repository:

```sh
docker pull python:3.12-slim
python3 server.py
```

Open <http://localhost:3033>. Each move runs the accepted Python module in a fresh container with no network, no mounts, a read-only root, no capabilities, and process/memory/CPU limits. The server checks the accepted source digest before execution. A changed module requires acceptance again.

Choose **Load merge edge case**, then **Compare left move with binary**. This executes the original native library and recovered Python module separately, now; it does not replay a saved answer. `[2, 2, 4, 0]` must become `[4, 4, 0, 0]` with a score increment of 4, rather than incorrectly becoming `[8, 0, 0, 0]`.

**New game** adds random spawning in the browser. Random spawning and this interface are application code; they are outside the recovered contract.

The bundled reference library is Linux ARM64. On another architecture, compile the unchanged reference into a native shared library and use it with `tools/verify.py --native-library PATH`. The game comparison endpoint currently expects the bundled ARM64 artifact.

## What crosses the boundary

```text
GitHub contract
  → real Crusoe planning
  → native Hermes in OpenShell
  → REA / Ghidra decompilation + native runtime capture
  → Python engine + agent tests + child review
  → independent native differential checks
  → reviewed Git commit / PR / CI
  → browser game using the accepted source digest
```

`engine.py` exports two pure functions:

- `slide(row)` returns `row`, `score_delta`, and `moved` for a leftward row movement.
- `move(board, direction)` returns `board`, `score_delta`, and `moved` for a row-major board and one of `left`, `right`, `up`, or `down`.

Both functions reject malformed arguments and preserve the input. The recovered module has no dependency on the original executable or library.

## Independent acceptance

```sh
python3 -m unittest discover -s tests -v
python3 tools/verify.py
python3 tools/verify.py --holdout --seed 77173291 --output evidence/holdout.json
```

The development evaluation covers all 2,401 four-tile rows from `{0, 2, 4, 8, 16, 32, 64}`, 500 randomized boards in all four directions, five explicit edge cases, and 21 invalid-input cases. A second evaluation uses 2,401 randomized rows and fresh randomized boards, including larger values through `2**20`. The five edge cases and invalid-input checks repeat. The original C functions supply expected movement, score, and change status; invalid input behavior comes from the product contract.

`tools/oracle.py` adapts value representation and board orientation only. It calls the unchanged native functions through `ctypes`; it contains no movement algorithm. Expected outputs are computed in a separate process. Candidate evaluation has neither the native library nor the expected answers mounted.

The CI workflow compiles the same pinned C source for the GitHub runner architecture, runs the agent tests, and repeats independent parity in Docker. Retained local evidence describes the particular local run; CI produces fresh artifacts.

## Rerun native recovery

On the configured hackathon workstation, with the installed NemoHermes worker, REA service, Crusoe key and AYA controller code:

```sh
python3 tools/recover.py --factory ../onyx/aya
```

Run only while the dedicated `aya-feature` worker is idle. The current prototype serializes native jobs and reuses one sandbox with new work directories. The command freezes the live issue, validates the reference hashes, makes new model/tool calls, collects native audit records, and accepts a candidate only after independent evaluation. Failed candidates remain under `.work/`; they do not replace the accepted engine. It prepares a reviewable local change; GitHub delivery remains an explicit step.

The replayed local process is not a new sandbox per request. Docker Desktop reports Landlock unavailable. No claim of that boundary is made.

## Scope and attribution

This recovers **tile movement, merge ordering, and scoring**. It does not reconstruct an entire game, recover unknown assets, run a Windows binary, or demonstrate general recovery from stripped commercial code. Symbols are retained in the reference. 2048 is a familiar algorithm; the evidence establishes fidelity to the pinned executable, not that a model could not implement the mechanic from prior knowledge.

The native source and artifacts retain Maurits van der Schee's MIT notice in [reference/LICENSE](reference/LICENSE). New application and verification code is MIT licensed. REA, Ghidra, Hermes, NemoClaw/OpenShell, Crusoe and the original game retain their own attribution and licenses.

The contribution being tested is the enforced boundary between candidate generation, independent verification, and integration. This repository contains no unsupported claim that another coding assistant must fail the task.
