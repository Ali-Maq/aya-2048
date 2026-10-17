"""Thin ctypes adapter to unchanged upstream native functions; no merge algorithm."""

import ctypes
import json
import os
import sys
from pathlib import Path

path = Path(
    os.environ.get("AYA_REFERENCE_LIBRARY", "/reference/lib2048-linux-aarch64.so")
)
lib = ctypes.CDLL(str(path))
Row = ctypes.c_uint8 * 4
Board = Row * 4
lib.slideArray.argtypes = [
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.POINTER(ctypes.c_uint32),
]
lib.slideArray.restype = ctypes.c_bool
for direction in ["Left", "Right", "Up", "Down"]:
    fn = getattr(lib, "move" + direction)
    fn.argtypes = [ctypes.POINTER(Row), ctypes.POINTER(ctypes.c_uint32)]
    fn.restype = ctypes.c_bool


def exponent(value):
    return value.bit_length() - 1 if value else 0


def observe(item):
    score = ctypes.c_uint32(0)
    if item["kind"] == "slide":
        row = Row(*(exponent(v) for v in item["row"]))
        moved = lib.slideArray(row, ctypes.byref(score))
        return {
            "row": [1 << v if v else 0 for v in row],
            "score_delta": score.value,
            "moved": bool(moved),
        }
    original = item["board"]
    # Upstream memory is board[x][y]; public contract is rows[y][x].
    board = Board(
        *(Row(*(exponent(original[y][x]) for y in range(4))) for x in range(4))
    )
    moved = getattr(lib, "move" + item["direction"].title())(board, ctypes.byref(score))
    return {
        "board": [
            [1 << board[x][y] if board[x][y] else 0 for x in range(4)] for y in range(4)
        ],
        "score_delta": score.value,
        "moved": bool(moved),
    }


if __name__ == "__main__":
    print(json.dumps([observe(item) for item in json.load(sys.stdin)]))
