# SOKOBAN Solver

This program solves the warehouse box-pushing puzzle. The program uses A\*
search with deadlock detection. A window shows each move that the program
finds.

The program needs Python 3.9 or a later version. The program uses only the
standard library. No installation step is necessary.

```bash
python main.py
```

## What the program does

A worker pushes boxes across a grid of squares. Each box must stop on a
target. The worker pushes a box only from the opposite side. The worker cannot
pull a box. One incorrect push can make the level impossible.

The program finds the shortest sequence of pushes. Then the program shows each
move in the window.

## How to run the program

1. Open a terminal.
2. Go to the project folder.
3. Type `python main.py`.

The window opens at the first level.

## How to use the window

1. Select a level from the list.
2. Click **Solve**, or press **Enter**.
3. Wait for the search. The status line counts the positions.
4. Watch the replay. A box becomes green when the box stops on a target.

Press **Space** to stop the replay. Press **Space** again to continue. Press
**R** to put the level back to the start position.

Use the arrow keys or the W, A, S and D keys to move the worker. The program
starts the search from the current position. Thus you can push some boxes
yourself, and then let the program complete the level.

| Control | Key | Function |
|---|---|---|
| Level list | — | Selects a level and resets the board |
| Solve | Enter | Starts the search; a second click stops the search |
| Play / Pause | Space | Stops and continues the replay |
| Reset | R | Puts the level back to the start position |
| Move the worker | Arrows or W A S D | Moves one square, and pushes a box if a box is in the way |

## The rules

| Symbol | Meaning |
|---|---|
| `#` | Wall |
| (space) | Floor |
| `.` | Target |
| `$` | Box |
| `*` | Box on a target |
| `@` | Worker |
| `+` | Worker on a target |

A push is legal only in these two conditions:

- The worker can walk to the square opposite the box.
- The square beyond the box is empty.

The level is complete when each box is on a target.

## How the solver works

Sokoban is PSPACE-complete. A search of all the moves is too slow. Three
methods make the search small enough.

### The search examines pushes, not steps

The path of the worker between two pushes has no effect on the result. Thus
the search examines only box pushes. The program calculates the path of the
worker at the end. The cost of a solution is the number of pushes.

### Equal positions become one node

Two positions that have the same boxes are equal, if the worker can walk from
one worker square to the other. Thus the program identifies a position by the
boxes and by the top left square of the area of the worker. This makes the
number of positions much smaller.

### The program removes lost positions

Many positions cannot give a solution. The program finds two types of lost
position.

**Simple deadlock.** The box is on a square from which no target is possible.
This type of square is a dead square. A corner is an example. The wall between
two corners is also an example. The program finds all the dead squares before
the search starts. One lookup is then sufficient.

**Freeze deadlock.** The box cannot move on the horizontal axis, and the box
cannot move on the vertical axis. Walls, dead squares or other boxes hold the
box. If this box is not on a target, the level is lost. The test is recursive,
because box A can hold box B while box B holds box A.

On the largest level, these two tests remove 11,472 positions.

### The estimate

Before the search, the program pulls one box backwards out of each target.
This gives the number of pushes from each square to that target. Other boxes
can only increase this number. Thus the estimate is never too large, and A\*
finds the shortest solution.

Each box needs a different target. The program matches the boxes to the
targets with the Hungarian algorithm. The cost is O(n³) for n boxes, which is
small compared to the search. A simpler estimate gives each box the nearest
target. That estimate examines 7 times more positions on the largest level.

## Results

| Level | Boxes | Pushes | Moves | Positions | Time |
|---|---|---|---|---|---|
| First Push | 1 | 1 | 2 | 2 | 0.00 s |
| Side by Side | 2 | 2 | 7 | 3 | 0.00 s |
| Around the Pillar | 2 | 2 | 11 | 3 | 0.00 s |
| The Hallway | 2 | 6 | 27 | 7 | 0.00 s |
| Long Way Round | 1 | 9 | 22 | 10 | 0.00 s |
| Crossroads | 4 | 4 | 18 | 5 | 0.00 s |
| The Vault | 4 | 4 | 33 | 5 | 0.00 s |
| Pinwheel | 4 | 4 | 12 | 5 | 0.00 s |
| Storage Room | 4 | 20 | 78 | 36 | 0.01 s |
| The Depot | 3 | 21 | 79 | 39 | 0.00 s |
| Tight Fit | 4 | 10 | 49 | 11 | 0.00 s |
| Warehouse Shift | 5 | 28 | 117 | 5,539 | 1.96 s |

Each push count in the table is the shortest possible count. The program
replayed each solution against the rules to prove that the solution is
correct.

## The files

```
main.py                 Starts the window
sokoban/game.py         The rules: walls, targets, moves, pushes, level files
sokoban/solver.py       Distances, deadlock tests, the match, the A* search
sokoban/gui.py          The window, the search thread, the replay
levels/levels.sok       Twelve levels
tests/test_sokoban.py   25 tests
```

The modules depend in one direction only: `gui` uses `solver`, and `solver`
uses `game`. The `game` module knows nothing about the search. The `solver`
module knows nothing about the window. Thus a test can run the solver without
a screen.

## The level file

The file `levels/levels.sok` holds the levels. An empty line separates two
levels. A line that starts with `;` gives the name of the next level. The
symbols are the same as the table above.

To add a level, open the file in a text editor and add a block:

```
; 13. My Level
#######
#  .  #
# $$  #
#  .@ #
#######
```

The program rejects a level that breaks one of these rules:

- The level has exactly one worker.
- The level has one box as a minimum.
- The number of boxes is not more than the number of targets.
- Walls fully enclose the floor.

## Tests

```bash
python -m unittest discover -s tests -v
```

The 25 tests examine the level parser, the legal moves, the two deadlock
tests, the match algorithm and the full search. For each level, the test
replays the solution against the rules. Thus the solver cannot approve its own
result.

## Limits

- The program counts the cost in pushes. The path of the worker between two
  pushes is the shortest path, but the total number of moves is not the
  minimum.
- The program finds simple deadlocks and freeze deadlocks. The program does
  not find corral deadlocks.
- A level with 20 boxes or more can stop at the limit of 2,000,000 positions
  or 60 seconds.

## Author

Rana Rishith
