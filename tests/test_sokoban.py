"""Tests.  Run with ``python -m unittest discover -s tests -v``."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sokoban.game import Board, LevelError, State, load_levels, parse_collection  # noqa: E402
from sokoban.solver import UNREACHABLE, Analysis, min_cost_assignment, solve, verify  # noqa: E402

TRIVIAL = "#####\n#@  #\n# $.#\n#   #\n#####"
CORNER_TRAP = "#######\n#@    #\n#  $  #\n#    .#\n#######"


def level(text: str) -> Board:
    return parse_collection(text)[0]


class ParsingTests(unittest.TestCase):
    def test_parses_pieces(self) -> None:
        board = level(TRIVIAL)
        self.assertEqual(board.initial.player, (1, 1))
        self.assertEqual(board.initial.boxes, frozenset({(2, 2)}))
        self.assertEqual(board.goals, frozenset({(2, 3)}))

    def test_player_on_goal_counts_as_a_goal(self) -> None:
        board = level("#####\n#$+.#\n#####")
        self.assertEqual(board.goals, frozenset({(1, 2), (1, 3)}))
        self.assertEqual(board.initial.player, (1, 2))

    def test_rejects_unenclosed_level(self) -> None:
        with self.assertRaises(LevelError):
            level("###\n#@$.\n###")

    def test_rejects_missing_player(self) -> None:
        with self.assertRaises(LevelError):
            level("#####\n# $.#\n#####")

    def test_rejects_more_boxes_than_goals(self) -> None:
        with self.assertRaises(LevelError):
            level("######\n#@$$.#\n######")

    def test_bundled_pack_loads_with_unique_titles(self) -> None:
        boards = load_levels()
        self.assertGreaterEqual(len(boards), 12)
        self.assertEqual(len({b.name for b in boards}), len(boards))


class MovementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.board = level(TRIVIAL)

    def test_walking_into_a_wall_is_blocked(self) -> None:
        self.assertIsNone(self.board.step(self.board.initial, "u"))

    def test_pushing_moves_both(self) -> None:
        pushed = self.board.step(self.board.step(self.board.initial, "d"), "r")
        self.assertEqual(pushed.player, (2, 2))
        self.assertEqual(pushed.boxes, frozenset({(2, 3)}))
        self.assertTrue(self.board.is_solved(pushed))

    def test_generated_pushes_are_legal(self) -> None:
        for push, successor in self.board.pushes(self.board.initial):
            self.assertIn(push.box_from, self.board.initial.boxes)
            self.assertIn(push.box_to, successor.boxes)
            self.assertNotIn(push.box_to, self.board.walls)

    def test_normalisation_collapses_equivalent_player_squares(self) -> None:
        boxes = self.board.initial.boxes
        self.assertEqual(
            self.board.normalize(State((1, 1), boxes)),
            self.board.normalize(State((3, 3), boxes)),
        )


class AnalysisTests(unittest.TestCase):
    def test_corners_are_dead_squares(self) -> None:
        analysis = Analysis(level(CORNER_TRAP))
        self.assertIn((1, 1), analysis.dead_squares)
        self.assertNotIn((2, 5), analysis.dead_squares)

    def test_distances_from_a_goal(self) -> None:
        board = level(CORNER_TRAP)
        analysis = Analysis(board)
        goal = next(iter(board.goals))
        self.assertEqual(analysis.distance(goal, goal), 0)
        self.assertEqual(analysis.distance((1, 1), goal), UNREACHABLE)

    def test_box_in_a_corner_is_a_deadlock(self) -> None:
        board = level(CORNER_TRAP)
        self.assertTrue(Analysis(board).is_deadlock(State((2, 2), frozenset({(1, 1)}))))

    def test_starting_position_is_fine(self) -> None:
        board = level(CORNER_TRAP)
        self.assertFalse(Analysis(board).is_deadlock(board.initial))

    def test_two_boxes_freezing_each_other_against_a_wall(self) -> None:
        board = level("######\n#@   #\n# $$ #\n#  . #\n#  . #\n######")
        frozen = State((2, 1), frozenset({(1, 2), (1, 3)}))
        self.assertTrue(Analysis(board).is_deadlock(frozen))

    def test_box_on_a_goal_is_never_a_deadlock(self) -> None:
        board = level("#####\n#@*.#\n#####")
        self.assertFalse(Analysis(board).is_deadlock(board.initial))


class AssignmentTests(unittest.TestCase):
    def test_avoids_the_greedy_trap(self) -> None:
        # Both rows want column 0; the real optimum pays 3 to free it up.
        self.assertEqual(min_cost_assignment([[1, 3], [1, 100]]), 4)

    def test_handles_more_columns_than_rows(self) -> None:
        self.assertEqual(min_cost_assignment([[5, 2, 9]]), 2)

    def test_empty_matrix(self) -> None:
        self.assertEqual(min_cost_assignment([]), 0)


class SolverTests(unittest.TestCase):
    def test_solves_verifies_and_stays_admissible_on_every_level(self) -> None:
        for board in load_levels():
            with self.subTest(level=board.name):
                result = solve(board)
                self.assertEqual(result.status, "solved")
                self.assertTrue(verify(board, result.moves))
                # Admissible: the start estimate cannot exceed the optimal
                # push count A* actually found.
                self.assertLessEqual(Analysis(board).heuristic(board.initial), result.pushes)

    def test_reports_unsolvable_rather_than_hanging(self) -> None:
        board = level("#######\n#@    #\n#   # #\n#  $# #\n#   #.#\n#######")
        self.assertEqual(solve(board).status, "unsolvable")

    def test_already_solved_position_needs_no_pushes(self) -> None:
        result = solve(level("#####\n#@*.#\n#####"))
        self.assertTrue(result.solved)
        self.assertEqual(result.pushes, 0)

    def test_search_stays_efficient(self) -> None:
        # Node counts are deterministic, so this is a real regression guard:
        # dropping the f-tie-break on h quietly costs about 5x here.
        result = solve(load_levels()[11])
        self.assertEqual(result.pushes, 28)
        self.assertLess(result.nodes, 10_000)

    def test_node_limit_aborts(self) -> None:
        self.assertEqual(solve(load_levels()[11], max_nodes=20).status, "aborted")

    def test_verify_rejects_a_wrong_answer(self) -> None:
        self.assertFalse(verify(level(TRIVIAL), "dd"))


if __name__ == "__main__":
    unittest.main()
