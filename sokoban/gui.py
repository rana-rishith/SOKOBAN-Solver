"""The window: push boxes around by hand, or watch the solver's plan replay.

The search runs on a worker thread and reports through a queue the Tk main loop
drains on a timer, so the window stays responsive on hard levels and Stop
actually stops.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from .game import Board, State, load_levels
from .solver import Result, solve

COLOURS = {
    "bg": "#15171c",
    "panel": "#1d2027",
    "text": "#d7dae1",
    "muted": "#8b93a3",
    "wall": "#39404f",
    "wall_edge": "#4a5365",
    "floor": "#242832",
    "goal": "#d8a33b",
    "box": "#c0783c",
    "box_done": "#4f9d58",
    "player": "#4f8ef7",
}

REPLAY_DELAY_MS = 90
KEYS = {"Up": "u", "Down": "d", "Left": "l", "Right": "r",
        "w": "u", "s": "d", "a": "l", "d": "r"}


class SokobanApp:
    def __init__(self, root: tk.Tk, boards: List[Board]) -> None:
        self.root = root
        self.boards = boards
        self.board = boards[0]
        self.state: State = self.board.initial
        self.moves_made = 0

        self.solution = ""
        self.solution_index = 0
        self.playing = False
        self._tick_id: Optional[str] = None

        self.results: "queue.Queue[Result]" = queue.Queue()
        self.cancelled = threading.Event()
        self.solving = False
        self.progress = 0  # written by the worker, read by the Tk timer

        self.status = tk.StringVar()
        self._build_ui()
        self.load_level(0)
        self.root.after(60, self._poll_solver)

    # ------------------------------------------------------------------- ui

    def _build_ui(self) -> None:
        root = self.root
        root.title("Sokoban Solver -- A* with deadlock detection")
        root.configure(bg=COLOURS["bg"])
        root.minsize(720, 520)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - platform dependent
            pass
        style.configure("TFrame", background=COLOURS["panel"])
        style.configure("TLabel", background=COLOURS["panel"], foreground=COLOURS["text"])
        style.configure("TButton", padding=(10, 5))

        sidebar = ttk.Frame(root, padding=14)
        sidebar.pack(side="left", fill="y")

        ttk.Label(sidebar, text="Level").pack(anchor="w")
        self.level_box = ttk.Combobox(
            sidebar, state="readonly", width=22, values=[b.name for b in self.boards]
        )
        self.level_box.pack(anchor="w", pady=(2, 16))
        self.level_box.bind(
            "<<ComboboxSelected>>", lambda _: self.load_level(self.level_box.current())
        )

        self.solve_button = ttk.Button(sidebar, text="Solve  (Enter)", command=self.solve)
        self.solve_button.pack(fill="x", pady=(0, 6))
        self.play_button = ttk.Button(sidebar, text="Play  (Space)", command=self.toggle_play)
        self.play_button.pack(fill="x", pady=(0, 6))
        ttk.Button(sidebar, text="Reset  (R)", command=self.reset).pack(fill="x")

        ttk.Label(
            sidebar, foreground=COLOURS["muted"], justify="left", wraplength=170,
            text="Arrow keys or WASD to push boxes yourself. Solve continues from "
                 "wherever you have got to.",
        ).pack(anchor="w", pady=(20, 0))

        area = tk.Frame(root, bg=COLOURS["bg"])
        area.pack(side="right", fill="both", expand=True)
        self.canvas = tk.Canvas(area, bg=COLOURS["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(12, 4))
        self.canvas.bind("<Configure>", lambda _: self.draw())
        tk.Label(
            area, textvariable=self.status, bg=COLOURS["bg"], fg=COLOURS["text"],
            anchor="w", font=("Segoe UI", 10),
        ).pack(fill="x", padx=16, pady=(0, 12))

        root.bind("<Key>", self.on_key)

    # ---------------------------------------------------------------- state

    def load_level(self, index: int) -> None:
        self.cancelled.set()
        index = max(0, min(index, len(self.boards) - 1))
        self.board = self.boards[index]
        self.level_box.current(index)
        self.reset()

    def reset(self) -> None:
        self.stop_playing()
        self.state = self.board.initial
        self.moves_made = 0
        self.solution = ""
        self.solution_index = 0
        self.draw()
        self.report()

    def do_move(self, direction: str) -> bool:
        nxt = self.board.step(self.state, direction)
        if nxt is None:
            return False
        self.state = nxt
        self.moves_made += 1
        self.draw()
        self.report()
        return True

    def on_key(self, event: tk.Event) -> None:
        key = event.keysym
        direction = KEYS.get(key) or KEYS.get(key.lower())
        if direction:
            self.stop_playing()
            self.solution = ""  # the plan no longer lines up with the position
            self.do_move(direction)
        elif key.lower() == "r":
            self.reset()
        elif key in ("Return", "KP_Enter"):
            self.solve()
        elif key == "space":
            self.toggle_play()

    def report(self) -> None:
        if self.solving:
            return
        placed = len(self.state.boxes & self.board.goals)
        line = f"{placed}/{len(self.state.boxes)} boxes on target  ·  {self.moves_made} moves"
        if self.solution:
            line += f"  ·  replaying {self.solution_index}/{len(self.solution)}"
        self.status.set("Solved!  " + line if self.board.is_solved(self.state) else line)

    # -------------------------------------------------------------- solving

    def solve(self) -> None:
        if self.solving:
            self.cancelled.set()
            return
        self.stop_playing()
        self.solution = ""
        self.solving = True
        self.cancelled.clear()
        self.solve_button.configure(text="Stop")
        self.status.set("Searching…")

        board, state = self.board, self.state

        def run() -> None:
            # Touching Tk off the main thread is not safe, so just park the
            # count where the timer below can pick it up.
            self.results.put(
                solve(
                    board, state,
                    cancel=self.cancelled.is_set,
                    on_progress=lambda partial: setattr(self, "progress", partial.nodes),
                )
            )

        threading.Thread(target=run, daemon=True).start()

    def _poll_solver(self) -> None:
        try:
            while True:
                self._solved(self.results.get_nowait())
        except queue.Empty:
            if self.solving and self.progress:
                self.status.set(f"Searching… {self.progress:,} positions examined")
        self.root.after(60, self._poll_solver)

    def _solved(self, result: Result) -> None:
        self.solving = False
        self.progress = 0
        self.solve_button.configure(text="Solve  (Enter)")
        if self.cancelled.is_set():
            # Stopped by the user, or the level changed under it.
            self.report()
            return
        if result.solved:
            self.solution = result.moves
            self.solution_index = 0
            self.status.set(
                f"Solved in {result.pushes} pushes, {len(result.moves)} moves"
                f"  ·  {result.summary()}"
            )
            self.start_playing()
        elif result.status == "unsolvable":
            self.status.set(f"No solution from this position  ·  {result.summary()}")
        else:
            self.status.set(f"Stopped  ·  {result.summary()}")

    # --------------------------------------------------------------- replay

    def toggle_play(self) -> None:
        if self.playing:
            self.stop_playing()
        else:
            self.start_playing()

    def start_playing(self) -> None:
        if self.solution_index >= len(self.solution):
            return
        self.playing = True
        self.play_button.configure(text="Pause  (Space)")
        self._tick()

    def stop_playing(self) -> None:
        self.playing = False
        if self._tick_id is not None:
            self.root.after_cancel(self._tick_id)
            self._tick_id = None
        self.play_button.configure(text="Play  (Space)")

    def _tick(self) -> None:
        if not self.playing or not self.step_forward():
            self.stop_playing()
            return
        self._tick_id = self.root.after(REPLAY_DELAY_MS, self._tick)

    def step_forward(self) -> bool:
        if self.solution_index >= len(self.solution):
            return False
        if not self.do_move(self.solution[self.solution_index].lower()):
            return False  # pragma: no cover - solver bug guard
        self.solution_index += 1
        self.report()  # do_move reported before the index moved
        return True

    # -------------------------------------------------------------- drawing

    def draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 10 or height < 10:
            return

        board = self.board
        cell = max(8, min(width // board.width, height // board.height))
        x0 = (width - cell * board.width) // 2
        y0 = (height - cell * board.height) // 2

        for r in range(board.height):
            for c in range(board.width):
                pos = (r, c)
                left, top = x0 + c * cell, y0 + r * cell
                if pos in board.walls:
                    canvas.create_rectangle(
                        left, top, left + cell, top + cell,
                        fill=COLOURS["wall"], outline=COLOURS["wall_edge"],
                    )
                    continue
                if pos not in board.floors:
                    continue  # outside the playable area
                canvas.create_rectangle(
                    left, top, left + cell, top + cell, fill=COLOURS["floor"], outline=""
                )
                if pos in board.goals:
                    inset = cell // 3
                    canvas.create_oval(
                        left + inset, top + inset, left + cell - inset, top + cell - inset,
                        outline=COLOURS["goal"], width=max(2, cell // 14),
                    )

        pad = max(2, cell // 10)
        for r, c in self.state.boxes:
            left, top = x0 + c * cell + pad, y0 + r * cell + pad
            canvas.create_rectangle(
                left, top, left + cell - 2 * pad, top + cell - 2 * pad,
                fill=COLOURS["box_done"] if (r, c) in board.goals else COLOURS["box"], outline="",
            )

        r, c = self.state.player
        inset = max(3, cell // 6)
        canvas.create_oval(
            x0 + c * cell + inset, y0 + r * cell + inset,
            x0 + (c + 1) * cell - inset, y0 + (r + 1) * cell - inset,
            fill=COLOURS["player"], outline="",
        )


def run() -> None:
    root = tk.Tk()
    root.geometry("900x620")
    SokobanApp(root, load_levels())
    root.mainloop()
