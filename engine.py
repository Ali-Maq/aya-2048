"""Pure-Python 2048 slide/move engine.

Recovered from the reference C implementation (mevdschee/2048.c, compiled as
2048-linux-aarch64 / lib2048-linux-aarch64.so) by decompiling slideArray and
findTarget and validating against native runtime output.

Semantics (faithful to the native binary):
  * The board holds tile *values* (0 or powers of two), not exponents.
  * slide(row) performs a single "move left" pass with greedy merges: a tile
    moves as far left as an empty cell or an equal-valued cell allows; a tile
    merges at most once per slide (enforced by a "stop" index past the last
    merge).  Merging two equal values v yields 2v and adds 2v to the score.
  * move(board, direction) maps right/up/down onto a left slide via reversal
    and transposition, exactly as rotateBoard (90-deg counter-clockwise)
    + slideArray + the inverse rotation do in the binary.
"""

from typing import List

MAX_EXPONENT = 20
MAX_TILE = 1 << MAX_EXPONENT
_DIRECTIONS = ("left", "right", "up", "down")


def _validate_tile(value):
    if type(value) is not int:
        raise ValueError("tile must be an exact integer, got %r" % (value,))
    if value == 0:
        return
    if value < 2 or value > MAX_TILE or (value & (value - 1)) != 0:
        raise ValueError(
            "tile must be a power of two from 2 through 2**20, got %r" % (value,)
        )


def _validate_row(row):
    if type(row) is not list or len(row) != 4:
        raise ValueError("row must be a list of length 4")
    for v in row:
        _validate_tile(v)


def _validate_board(board):
    if type(board) is not list or len(board) != 4:
        raise ValueError("board must be a list of 4 rows")
    for row in board:
        _validate_row(row)


def _find_target(b, i, stop):
    """Leftmost target index for the tile at position i, mirroring findTarget.

    stop is the index just past the most recent merge (0 initially), which
    prevents a merged cell from merging again within a single slide.
    """
    if i == 0:
        return 0
    j = i - 1
    while b[j] == 0:
        if stop == j:
            return stop
        j -= 1
    target = j + 1
    if b[i] == b[j]:
        target = j
    return target


def slide(row):
    """Slide one row left (no random spawn).

    Returns {row: List[int] (4 tiles), score_delta: int, moved: bool}.
    Does not mutate the input.
    """
    _validate_row(row)
    b = list(row)
    score_delta = 0
    moved = False
    stop = 0
    for i in range(4):
        v = b[i]
        if v == 0:
            continue
        target = _find_target(b, i, stop)
        if target == i:
            continue
        if b[target] == 0:
            b[target] = v
        elif b[target] == v:
            b[target] = v + v
            score_delta += b[target]
            stop = target + 1
        b[i] = 0
        moved = True
    return {"row": b, "score_delta": score_delta, "moved": moved}


def move(board, direction):
    """Move the whole 4x4 board in the given direction (no random spawn).

    direction is one of "left", "right", "up", "down".
    Returns {board: List[List[int]], score_delta: int, moved: bool}.
    Does not mutate the input.
    """
    _validate_board(board)
    if direction not in _DIRECTIONS:
        raise ValueError(
            "direction must be one of %r, got %r" % (_DIRECTIONS, direction)
        )

    b = [list(r) for r in board]
    score_delta = 0
    moved = False

    if direction == "left":
        for r in range(4):
            res = slide(b[r])
            b[r] = res["row"]
            score_delta += res["score_delta"]
            moved = moved or res["moved"]
    elif direction == "right":
        for r in range(4):
            rev = list(reversed(b[r]))
            res = slide(rev)
            b[r] = list(reversed(res["row"]))
            score_delta += res["score_delta"]
            moved = moved or res["moved"]
    elif direction == "up":
        for c in range(4):
            col = [b[r][c] for r in range(4)]
            res = slide(col)
            for r in range(4):
                b[r][c] = res["row"][r]
            score_delta += res["score_delta"]
            moved = moved or res["moved"]
    else:  # down
        for c in range(4):
            col = [b[3 - r][c] for r in range(4)]
            res = slide(col)
            for r in range(4):
                b[3 - r][c] = res["row"][r]
            score_delta += res["score_delta"]
            moved = moved or res["moved"]

    return {"board": b, "score_delta": score_delta, "moved": moved}