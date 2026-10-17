"""Observe the reference functions without reimplementing movement."""

import ctypes
import hashlib
import json
import os
from pathlib import Path

LIB = Path(
    os.environ.get(
        "AYA_REFERENCE_LIBRARY", "/reference/game-2048/lib2048-linux-aarch64.so"
    )
)
lib = ctypes.CDLL(str(LIB))
lib.slideArray.argtypes = [
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.POINTER(ctypes.c_uint32),
]
lib.slideArray.restype = ctypes.c_bool
rows = [[2, 2, 2, 2], [4, 0, 4, 4], [2, 2, 4, 0], [0, 0, 0, 0], [2, 4, 8, 16]]
results = []
for row in rows:
    array = (ctypes.c_uint8 * 4)(*(x.bit_length() - 1 if x else 0 for x in row))
    score = ctypes.c_uint32(0)
    moved = lib.slideArray(array, ctypes.byref(score))
    results.append(
        {
            "input": row,
            "row": [1 << x if x else 0 for x in array],
            "score_delta": score.value,
            "moved": bool(moved),
        }
    )
print(
    json.dumps(
        {
            "library_sha256": hashlib.sha256(LIB.read_bytes()).hexdigest(),
            "results": results,
        }
    )
)
