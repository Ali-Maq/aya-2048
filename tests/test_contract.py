"""Controller-owned public contract checks; agent tests are a separate file."""

import copy
import unittest

from engine import move, slide


class Contract(unittest.TestCase):
    def test_merge_is_not_reused(self):
        self.assertEqual(
            slide([2, 2, 4, 0]), {"row": [4, 4, 0, 0], "score_delta": 4, "moved": True}
        )

    def test_disjoint_pairs_score(self):
        self.assertEqual(
            slide([2, 2, 2, 2]), {"row": [4, 4, 0, 0], "score_delta": 8, "moved": True}
        )

    def test_noop_has_zero_score(self):
        self.assertEqual(
            slide([2, 4, 8, 16]),
            {"row": [2, 4, 8, 16], "score_delta": 0, "moved": False},
        )

    def test_row_major_vertical_movement(self):
        board = [[2, 0, 0, 0], [2, 0, 0, 0], [4, 0, 0, 0], [0, 0, 0, 0]]
        before = copy.deepcopy(board)
        self.assertEqual(
            move(board, "up"),
            {
                "board": [[4, 0, 0, 0], [4, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
                "score_delta": 4,
                "moved": True,
            },
        )
        self.assertEqual(board, before)

    def test_invalid_values_fail_before_mutation(self):
        for value in [True, 2.0, -2, 3, 1, "2", 2**21]:
            row = [2, 2, 0, value]
            before = row[:]
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    slide(row)
                self.assertEqual(row, before)

    def test_direction_is_not_coerced(self):
        for direction in ["LEFT", "diagonal", None, 0]:
            with self.subTest(direction=direction):
                with self.assertRaises(ValueError):
                    move([[0] * 4 for _ in range(4)], direction)


if __name__ == "__main__":
    unittest.main()
