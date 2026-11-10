"""The rules: walls, goals, state, legal moves, and .sok parsing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Iterator, List, Optional, Sequence, Set, Tuple

Pos = Tuple[int, int]

#: Row/column deltas, keyed by the letter used in LURD solution strings.
DIRECTIONS: Dict[str, Pos] = {"u": (-1, 0), "d": (1, 0), "l": (0, -1), "r": (0, 1)}

LEVELS_FILE = Path(__file__).resolve().parent.parent / "levels" / "levels.sok"


class LevelError(ValueError):
    """A level cannot be parsed into something playable."""


@dataclass(frozen=True)
class State:
    """Everything that changes while a level is played."""

    player: Pos
    boxes: FrozenSet[Pos]


@dataclass(frozen=True)
class Push:
    """The box on ``box_from`` moves one step along ``direction``."""

    box_from: Pos
    direction: str

    @property
    def box_to(self) -> Pos:
        dr, dc = DIRECTIONS[self.direction]
        return (self.box_from[0] + dr, self.box_from[1] + dc)

    @property
    def player_from(self) -> Pos:
        dr, dc = DIRECTIONS[self.direction]
        return (self.box_from[0] - dr, self.box_from[1] - dc)


class Board:
    """The fixed half of a level, plus move generation over it."""

    def __init__(self, rows: Sequence[str], name: str = "unnamed") -> None:
        if not rows:
            raise LevelError("level is empty")
        self.name = name
        self.height = len(rows)
        self.width = max(len(row) for row in rows)
        rows = [row.ljust(self.width) for row in rows]  # .sok rows are often ragged

        walls: Set[Pos] = set()
        goals: Set[Pos] = set()
        boxes: List[Pos] = []
        player: Optional[Pos] = None

        for r, row in enumerate(rows):
            for c, char in enumerate(row):
                pos = (r, c)
                if char == "#":
                    walls.add(pos)
                elif char in ".*+":
                    goals.add(pos)
                elif char not in "$@ -_":
                    raise LevelError(f"unexpected character {char!r} at row {r}, column {c}")
                if char in "$*":
                    boxes.append(pos)
                if char in "@+":
                    if player is not None:
                        raise LevelError("level has more than one player")
                    player = pos

        if player is None:
            raise LevelError("level has no player")
        if not boxes:
            raise LevelError("level has no boxes")
        if len(boxes) > len(goals):
            raise LevelError(f"{len(boxes)} boxes but only {len(goals)} goals -- unsolvable")

        self.walls: FrozenSet[Pos] = frozenset(walls)
        self.goals: FrozenSet[Pos] = frozenset(goals)
        self.initial = State(player, frozenset(boxes))
        self.floors: FrozenSet[Pos] = frozenset(self._flood_fill(player))

        stranded = [b for b in boxes if b not in self.floors]
        if stranded:
            raise LevelError(f"box at {stranded[0]} is walled off from the player")

    def _flood_fill(self, start: Pos) -> Set[Pos]:
        """Squares the player could stand on if boxes were not in the way.

        Doubles as the "is this level enclosed?" check -- escaping the grid
        means the border has a hole and the player could walk off into nothing.
        """
        seen = {start}
        queue = deque([start])
        while queue:
            r, c = queue.popleft()
            for dr, dc in DIRECTIONS.values():
                nr, nc = neighbour = (r + dr, c + dc)
                if not (0 <= nr < self.height and 0 <= nc < self.width):
                    raise LevelError("level is not fully enclosed by walls")
                if neighbour in seen or neighbour in self.walls:
                    continue
                seen.add(neighbour)
                queue.append(neighbour)
        return seen

    def reachable(self, player: Pos, boxes: FrozenSet[Pos]) -> Set[Pos]:
        """Squares the player can walk to without pushing anything."""
        seen = {player}
        queue = deque([player])
        while queue:
            r, c = queue.popleft()
            for dr, dc in DIRECTIONS.values():
                neighbour = (r + dr, c + dc)
                if neighbour in seen or neighbour in self.walls or neighbour in boxes:
                    continue
                seen.add(neighbour)
                queue.append(neighbour)
        return seen

    def normalize(self, state: State) -> Tuple[Pos, FrozenSet[Pos]]:
        """Canonical key for the closed set.

        Two positions with the same boxes are the same node whenever the player
        can walk between them, so key on the top-left square of the player's
        reachable area instead of where they happen to stand.
        """
        return (min(self.reachable(state.player, state.boxes)), state.boxes)

    def pushes(self, state: State) -> Iterator[Tuple[Push, State]]:
        """Every legal push from ``state``, as ``(push, resulting state)``."""
        area = self.reachable(state.player, state.boxes)
        boxes = state.boxes
        for box in boxes:
            br, bc = box
            for direction, (dr, dc) in DIRECTIONS.items():
                if (br - dr, bc - dc) not in area:
                    continue
                destination = (br + dr, bc + dc)
                if destination in self.walls or destination in boxes:
                    continue
                # The player ends up where the box was.
                yield Push(box, direction), State(box, frozenset(boxes - {box} | {destination}))

    def step(self, state: State, direction: str) -> Optional[State]:
        """One keyboard move, pushing a box if one is in the way, else ``None``."""
        dr, dc = DIRECTIONS[direction]
        target = (state.player[0] + dr, state.player[1] + dc)
        if target in self.walls:
            return None
        if target in state.boxes:
            beyond = (target[0] + dr, target[1] + dc)
            if beyond in self.walls or beyond in state.boxes:
                return None
            return State(target, frozenset(state.boxes - {target} | {beyond}))
        return State(target, state.boxes)

    def is_solved(self, state: State) -> bool:
        return state.boxes <= self.goals

    def walk_path(self, start: Pos, target: Pos, boxes: FrozenSet[Pos]) -> Optional[str]:
        """Shortest walk between two squares, as lowercase LURD letters."""
        if start == target:
            return ""
        came_from: Dict[Pos, Tuple[Pos, str]] = {}
        seen = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            r, c = current
            for direction, (dr, dc) in DIRECTIONS.items():
                neighbour = (r + dr, c + dc)
                if neighbour in seen or neighbour in self.walls or neighbour in boxes:
                    continue
                seen.add(neighbour)
                came_from[neighbour] = (current, direction)
                if neighbour == target:
                    letters = []
                    node = neighbour
                    while node != start:
                        node, letter = came_from[node]
                        letters.append(letter)
                    return "".join(reversed(letters))
                queue.append(neighbour)
        return None

    def moves_for_pushes(self, state: State, pushes: Sequence[Push]) -> str:
        """Expand a push sequence into keystrokes the GUI can replay.

        Pushes are uppercase, walking is lowercase -- the usual LURD convention.
        """
        player = state.player
        boxes = state.boxes
        letters: List[str] = []
        for push in pushes:
            walk = self.walk_path(player, push.player_from, boxes)
            if walk is None:  # pragma: no cover - only reachable on a solver bug
                raise LevelError(f"cannot reach {push.player_from} to make {push}")
            letters.append(walk)
            letters.append(push.direction.upper())
            boxes = frozenset(boxes - {push.box_from} | {push.box_to})
            player = push.box_from
        return "".join(letters)


def parse_collection(text: str, source: str = "<string>") -> List[Board]:
    """Parse a .sok collection: levels split by blank lines, ``;`` lines are titles."""
    boards: List[Board] = []
    rows: List[str] = []
    title: Optional[str] = None
    pending: Optional[str] = None

    def flush() -> None:
        nonlocal rows, title
        if rows:
            name = title or f"Level {len(boards) + 1}"
            try:
                boards.append(Board(rows, name=name))
            except LevelError as error:
                raise LevelError(f"{source}: level {name!r} is invalid: {error}") from error
        rows = []
        title = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(";"):
            flush()  # a comment ends the current level and titles the next
            pending = stripped.lstrip("; ").strip() or None
            continue
        if not stripped:
            flush()
            continue
        if not rows:
            title, pending = pending, None
        rows.append(line)

    flush()
    return boards


def load_levels() -> List[Board]:
    """The bundled level pack."""
    return parse_collection(LEVELS_FILE.read_text(encoding="utf-8"), source=str(LEVELS_FILE))
