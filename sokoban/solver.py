"""A* over box pushes, with deadlock pruning.

Three things keep the search tractable:

* It branches on *box pushes*, not footsteps -- the walking between pushes
  never changes what is solvable, so it is reconstructed once at the end.
* Positions that differ only in where the player stands collapse to one node
  (see :meth:`Board.normalize`).
* Positions that are already lost are thrown out on sight (:class:`Analysis`).

Cost is counted in pushes, the standard measure for Sokoban solvers.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from .game import DIRECTIONS, Board, Pos, Push, State

#: Stands in for "no path exists".  Finite, so the matching below can use plain
#: integer arithmetic.
UNREACHABLE = 1_000_000

_AXES = (((0, -1), (0, 1)), ((-1, 0), (1, 0)))  # horizontal, vertical


class Analysis:
    """Per-level facts worked out once, before the search starts.

    All of it comes from pretending there is a single box on the board and
    *pulling* it backwards out of each goal -- the reverse of pushing it in.
    That gives, for every square, how many pushes a lone box needs to reach
    that goal.  Other boxes can only ever get in the way, so those numbers are
    a lower bound on the real cost and the heuristic built from them is
    admissible.
    """

    def __init__(self, board: Board) -> None:
        self.board = board
        self.goals: List[Pos] = sorted(board.goals)
        self.pull_distance = {goal: self._pull_distances_from(goal) for goal in self.goals}
        reachable_from_some_goal: Set[Pos] = set()
        for table in self.pull_distance.values():
            reachable_from_some_goal |= table.keys()
        #: Squares no goal can be reached from: corners, and the wall-hugging
        #: strips between two corners.  A box here can never be recovered.
        self.dead_squares = frozenset(board.floors - reachable_from_some_goal)

    def _pull_distances_from(self, goal: Pos) -> Dict[Pos, int]:
        # Pulling a box one square needs the square behind it and the one
        # behind that to be free, because the player walks backwards into them.
        distances = {goal: 0}
        queue = deque([goal])
        while queue:
            r, c = current = queue.popleft()
            for dr, dc in DIRECTIONS.values():
                box_to = (r + dr, c + dc)
                if box_to in distances or box_to not in self.board.floors:
                    continue
                if (r + 2 * dr, c + 2 * dc) in self.board.walls:
                    continue
                distances[box_to] = distances[current] + 1
                queue.append(box_to)
        return distances

    def distance(self, box: Pos, goal: Pos) -> int:
        return self.pull_distance[goal].get(box, UNREACHABLE)

    def heuristic(self, state: State) -> int:
        """Pushes still needed, lower bound.

        Every box needs its own goal, which makes this an assignment problem;
        solving it exactly beats letting each box pick its nearest goal by
        roughly 6x in nodes expanded.  Boxes already on a goal are included
        rather than pinned there, because an optimal solution is allowed to
        push one off and bring it back.
        """
        boxes = sorted(state.boxes)
        return min_cost_assignment(
            [[self.distance(box, goal) for goal in self.goals] for box in boxes]
        )

    def is_deadlock(self, state: State, last_box: Optional[Pos] = None) -> bool:
        """Whether this position is already lost.

        ``last_box`` is the box that just moved -- only it can have created a
        new deadlock, so passing it turns a whole-board scan into one check.
        """
        boxes = state.boxes
        for box in (last_box,) if last_box is not None else tuple(boxes):
            if box in self.board.goals:
                continue
            if box in self.dead_squares:
                return True
            if self._is_frozen(box, boxes, set()):
                return True
        return False

    def _is_frozen(self, box: Pos, boxes: FrozenSet[Pos], assumed: Set[Pos]) -> bool:
        """Whether ``box`` can never move along either axis again."""
        if box in assumed:
            # Box A can be frozen because B is and vice versa.  Assuming it
            # frozen while its own check runs terminates the recursion safely:
            # if the assumption is wrong the outer call reports not-frozen.
            return True
        assumed.add(box)
        try:
            return all(self._axis_blocked(box, axis, boxes, assumed) for axis in _AXES)
        finally:
            assumed.discard(box)

    def _axis_blocked(self, box, axis, boxes: FrozenSet[Pos], assumed: Set[Pos]) -> bool:
        r, c = box
        sides = [(r + dr, c + dc) for dr, dc in axis]
        if any(side in self.board.walls for side in sides):
            return True
        # Both sides dead: the box could move, but only onto a square it can
        # never come back from, so the position is lost either way.
        if all(side in self.dead_squares for side in sides):
            return True
        return any(side in boxes and self._is_frozen(side, boxes, assumed) for side in sides)


def min_cost_assignment(cost: Sequence[Sequence[int]]) -> int:
    """Cheapest way to give every row its own column (Hungarian algorithm).

    O(n^3) shortest-augmenting-path form with potentials.  Rows are boxes and
    columns are goals; there are never more boxes than goals, so the matrix may
    be wider than tall.  Indices are 1-based, with 0 as the path sentinel.
    """
    rows = len(cost)
    if rows == 0:
        return 0
    cols = len(cost[0])
    big = UNREACHABLE * (rows + cols + 1)
    u = [0] * (rows + 1)
    v = [0] * (cols + 1)
    match = [0] * (cols + 1)  # column -> row
    parent = [0] * (cols + 1)  # column -> previous column on the path

    for row in range(1, rows + 1):
        match[0] = row
        col = 0
        slack = [big] * (cols + 1)
        used = [False] * (cols + 1)
        while True:
            used[col] = True
            current_row = match[col]
            delta, next_col = big, 0
            for j in range(1, cols + 1):
                if used[j]:
                    continue
                reduced = cost[current_row - 1][j - 1] - u[current_row] - v[j]
                if reduced < slack[j]:
                    slack[j], parent[j] = reduced, col
                if slack[j] < delta:
                    delta, next_col = slack[j], j
            for j in range(cols + 1):
                if used[j]:
                    u[match[j]] += delta
                    v[j] -= delta
                else:
                    slack[j] -= delta
            col = next_col
            if match[col] == 0:
                break
        while col:  # walk the augmenting path back, flipping pairs
            match[col], col = match[parent[col]], parent[col]

    return sum(cost[match[j] - 1][j - 1] for j in range(1, cols + 1) if match[j])


@dataclass
class Result:
    """Outcome of one solve.

    ``status`` is ``solved``, ``unsolvable`` (the whole reachable state space
    was exhausted) or ``aborted`` (a limit was hit or the caller cancelled,
    which says nothing about whether a solution exists).
    """

    status: str
    moves: str = ""
    pushes: int = 0
    nodes: int = 0
    pruned: int = 0
    elapsed: float = 0.0

    @property
    def solved(self) -> bool:
        return self.status == "solved"

    def summary(self) -> str:
        return f"{self.nodes:,} nodes, {self.pruned:,} deadlocks pruned, {self.elapsed:.2f}s"


def solve(
    board: Board,
    state: Optional[State] = None,
    cancel: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[Result], None]] = None,
    max_nodes: int = 2_000_000,
    max_seconds: float = 60.0,
) -> Result:
    """A* from ``state`` (the level's start position by default)."""
    state = board.initial if state is None else state
    analysis = Analysis(board)
    started = time.perf_counter()
    result = Result("aborted")

    def finish(status: str, pushes: Sequence[Push] = ()) -> Result:
        result.status = status
        result.elapsed = time.perf_counter() - started
        result.pushes = len(pushes)
        result.moves = board.moves_for_pushes(state, pushes) if pushes else ""
        return result

    if board.is_solved(state):
        return finish("solved")
    if analysis.is_deadlock(state):
        return finish("unsolvable")

    start_key = board.normalize(state)
    came_from: Dict[object, Optional[Tuple[object, Push]]] = {start_key: None}
    best_cost: Dict[object, int] = {start_key: 0}
    closed: Set[object] = set()
    counter = 0
    # Ties on f are broken by lower h: among equally promising nodes, go for
    # the one nearest the goal first.  Worth ~5x in nodes expanded.
    start_h = analysis.heuristic(state)
    frontier = [(start_h, start_h, counter, state)]

    while frontier:
        if result.nodes % 2000 == 0:
            result.elapsed = time.perf_counter() - started
            if (cancel is not None and cancel()) or result.elapsed > max_seconds:
                return finish("aborted")
            if on_progress is not None and result.nodes:
                on_progress(result)
        if result.nodes >= max_nodes:
            return finish("aborted")

        _, _, _, current = heappop(frontier)
        key = board.normalize(current)
        if key in closed:
            continue
        closed.add(key)
        result.nodes += 1

        if board.is_solved(current):
            return finish("solved", _reconstruct(came_from, key))

        cost = best_cost[key] + 1
        for push, successor in board.pushes(current):
            if analysis.is_deadlock(successor, push.box_to):
                result.pruned += 1
                continue
            estimate = analysis.heuristic(successor)
            if estimate >= UNREACHABLE:
                result.pruned += 1  # some box has no goal it can still reach
                continue
            successor_key = board.normalize(successor)
            if successor_key in closed or best_cost.get(successor_key, cost + 1) <= cost:
                continue
            best_cost[successor_key] = cost
            came_from[successor_key] = (key, push)
            counter += 1
            heappush(frontier, (cost + estimate, estimate, counter, successor))

    return finish("unsolvable")


def _reconstruct(came_from, key) -> List[Push]:
    pushes: List[Push] = []
    entry = came_from[key]
    while entry is not None:
        parent_key, push = entry
        pushes.append(push)
        entry = came_from[parent_key]
    pushes.reverse()
    return pushes


def verify(board: Board, moves: str, state: Optional[State] = None) -> bool:
    """Replay a move string against the rules and report whether it solves the level."""
    current = board.initial if state is None else state
    for letter in moves:
        current = board.step(current, letter.lower())
        if current is None:
            return False
    return board.is_solved(current)
