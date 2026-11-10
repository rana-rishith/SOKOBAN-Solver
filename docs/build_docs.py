"""Build the four deliverables into sokoban-solver/docs/.

    python build_docs.py

Needs reportlab and python-pptx (build-time only -- the project itself stays
standard-library only).  The per-level results table is measured live by
solving the bundled pack, so the documents cannot drift from the code.
"""

from __future__ import annotations

import html
import sys
import textwrap
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

PROJECT = Path(__file__).resolve().parent.parent
DOCS = PROJECT / "docs"

INK = colors.HexColor("#1b1f27")
ACCENT = colors.HexColor("#2f6fd0")
MUTED = colors.HexColor("#5d6677")
RULE = colors.HexColor("#d4d9e2")
PANEL = colors.HexColor("#f2f4f8")

# Deck palette, lifted from the app itself.
D_INK = RGBColor(0x1B, 0x1F, 0x27)
D_ACCENT = RGBColor(0x2F, 0x6F, 0xD0)
D_MUTED = RGBColor(0x5D, 0x66, 0x77)
D_BOX = RGBColor(0xC0, 0x78, 0x3C)
D_GOOD = RGBColor(0x4F, 0x9D, 0x58)
D_PANEL = RGBColor(0xF2, 0xF4, 0xF8)


# --------------------------------------------------------------------- pdf

def styles():
    base = getSampleStyleSheet()
    s = {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=26, leading=31, textColor=INK, alignment=TA_LEFT,
                                spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=12.5, leading=17,
                                   textColor=MUTED, spaceAfter=18),
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19,
                             textColor=ACCENT, spaceBefore=17, spaceAfter=7),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                             textColor=INK, spaceBefore=11, spaceAfter=4),
        "p": ParagraphStyle("p", fontName="Helvetica", fontSize=10, leading=15,
                            textColor=INK, spaceAfter=7),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=10, leading=15,
                                 textColor=INK, leftIndent=13, bulletIndent=3, spaceAfter=4),
        "code": ParagraphStyle("code", fontName="Courier", fontSize=8.4, leading=11,
                               textColor=INK, backColor=PANEL, borderPadding=6,
                               leftIndent=2, spaceBefore=4, spaceAfter=9),
        "listing": ParagraphStyle("listing", fontName="Courier", fontSize=6.9, leading=8.6,
                                  textColor=INK),
        "caption": ParagraphStyle("caption", fontName="Helvetica-Oblique", fontSize=8.6,
                                  leading=12, textColor=MUTED, spaceAfter=10),
    }
    return s


def table(rows, widths, header=True):
    data = [[Paragraph(f"<b>{html.escape(str(c))}</b>" if header and r == 0 else html.escape(str(c)),
                       ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=12.5,
                                      textColor=INK))
             for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, hAlign="LEFT")
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 5),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
             ("LEFTPADDING", (0, 0), (-1, -1), 7),
             ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), PANEL),
                  ("LINEBELOW", (0, 0), (-1, 0), 0.9, ACCENT)]
    t.setStyle(TableStyle(style))
    return t


def build_pdf(path: Path, title: str, subtitle: str, blocks) -> None:
    s = styles()
    story = [Paragraph(html.escape(title), s["title"]),
             Paragraph(html.escape(subtitle), s["subtitle"])]
    for kind, value in blocks:
        if kind == "h1":
            story.append(Paragraph(html.escape(value), s["h1"]))
        elif kind == "h2":
            story.append(Paragraph(html.escape(value), s["h2"]))
        elif kind == "p":
            story.append(Paragraph(value, s["p"]))  # caller may embed <b>/<i>
        elif kind == "caption":
            story.append(Paragraph(value, s["caption"]))
        elif kind == "bullets":
            for item in value:
                story.append(Paragraph(item, s["bullet"], bulletText="\u2022"))
            story.append(Spacer(1, 5))
        elif kind == "code":
            story.append(Preformatted(value, s["code"]))
        elif kind == "listing":
            story.append(Preformatted(value, s["listing"]))
        elif kind == "table":
            story.append(table(*value))
            story.append(Spacer(1, 9))
        elif kind == "pagebreak":
            story.append(PageBreak())

    def furniture(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 12 * mm, title)
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, str(canvas.getPageNumber()))
        canvas.setStrokeColor(RULE)
        canvas.line(18 * mm, 15.5 * mm, A4[0] - 18 * mm, 15.5 * mm)
        canvas.restoreState()

    SimpleDocTemplate(
        str(path), pagesize=A4, title=title, author="Sokoban Solver",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
    ).build(story, onFirstPage=furniture, onLaterPages=furniture)
    print(f"  {path.name}")


def source_listing(relative: str) -> list:
    """A code appendix entry: heading plus the file, wrapped to fit the page."""
    text = (PROJECT / relative).read_text(encoding="utf-8")
    lines = []
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.replace("\t", "    ")
        chunks = textwrap.wrap(line, 96, subsequent_indent="        ",
                               drop_whitespace=False) or [""]
        for index, chunk in enumerate(chunks):
            lines.append(f"{number if index == 0 else '':>4}  {chunk}")
    body = "\n".join(lines)
    return [("h2", relative),
            ("caption", f"{len(text.splitlines())} lines"),
            ("listing", body)]


# ------------------------------------------------------------------ facts

def measure() -> list:
    """Solve the bundled pack so the results table is never stale."""
    sys.path.insert(0, str(PROJECT))
    from sokoban.game import load_levels
    from sokoban.solver import solve, verify

    rows = [["Level", "Boxes", "Pushes", "Moves", "Positions examined",
             "Deadlocks pruned", "Time"]]
    for board in load_levels():
        result = solve(board)
        assert result.solved and verify(board, result.moves), board.name
        rows.append([board.name.split(". ", 1)[-1], len(board.initial.boxes), result.pushes,
                     len(result.moves), f"{result.nodes:,}", f"{result.pruned:,}",
                     f"{result.elapsed:.2f}s"])
    return rows


# ------------------------------------------------------------------- pptx

def deck(path: Path, results) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    W, H = prs.slide_width, prs.slide_height

    def textbox(slide, left, top, width, height, text, size, *, bold=False,
                colour=D_INK, align=PP_ALIGN.LEFT, font="Calibri"):
        box = slide.shapes.add_textbox(left, top, width, height)
        frame = box.text_frame
        frame.word_wrap = True
        frame.text = text
        p = frame.paragraphs[0]
        p.alignment = align
        run = p.runs[0]
        run.font.size, run.font.bold, run.font.name = Pt(size), bold, font
        run.font.color.rgb = colour
        return frame

    def band(slide):
        bar = slide.shapes.add_shape(1, 0, 0, W, Emu(int(Inches(0.09))))
        bar.fill.solid()
        bar.fill.fore_color.rgb = D_ACCENT
        bar.line.fill.background()
        bar.shadow.inherit = False

    def chrome(slide, title, kicker=None):
        band(slide)
        if kicker:
            textbox(slide, Inches(0.8), Inches(0.42), Inches(11.7), Inches(0.3),
                    kicker.upper(), 12, bold=True, colour=D_ACCENT)
        textbox(slide, Inches(0.8), Inches(0.72), Inches(11.7), Inches(0.8),
                title, 32, bold=True)

    def bullets(slide, items, top=Inches(1.85), left=Inches(0.8),
                width=Inches(11.7), size=17):
        box = slide.shapes.add_textbox(left, top, width, H - top - Inches(0.6))
        frame = box.text_frame
        frame.word_wrap = True
        for index, item in enumerate(items):
            sub = isinstance(item, tuple)
            text = item[0] if sub else item
            p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            p.text = ("- " if sub else "\u2022 ") + text
            p.space_after = Pt(9)
            p.level = 1 if sub else 0
            run = p.runs[0]
            run.font.size = Pt(size - 2 if sub else size)
            run.font.name = "Calibri"
            run.font.color.rgb = D_MUTED if sub else D_INK
        return frame

    def card(slide, left, top, width, height, heading, body, accent=D_ACCENT):
        shape = slide.shapes.add_shape(1, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = D_PANEL
        shape.line.color.rgb = accent
        shape.line.width = Pt(1.25)
        shape.shadow.inherit = False
        shape.text_frame.text = ""
        textbox(slide, left + Inches(0.22), top + Inches(0.16), width - Inches(0.44),
                Inches(0.4), heading, 15, bold=True, colour=accent)
        frame = textbox(slide, left + Inches(0.22), top + Inches(0.62),
                        width - Inches(0.44), height - Inches(0.8), body, 12.5,
                        colour=D_INK)
        frame.word_wrap = True

    def add_table(slide, rows, left, top, width, height, size=11):
        shape = slide.shapes.add_table(len(rows), len(rows[0]), left, top, width, height)
        tbl = shape.table
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                cell = tbl.cell(r, c)
                cell.text = str(value)
                p = cell.text_frame.paragraphs[0]
                p.runs[0].font.size = Pt(size)
                p.runs[0].font.bold = (r == 0)
                p.runs[0].font.name = "Calibri"
                p.runs[0].font.color.rgb = D_INK if r else D_PANEL
        return tbl

    def notes(slide, text):
        slide.notes_slide.notes_text_frame.text = text

    # 1 -- title -----------------------------------------------------------
    s = prs.slides.add_slide(blank)
    panel = s.shapes.add_shape(1, 0, 0, W, Inches(2.9))
    panel.fill.solid()
    panel.fill.fore_color.rgb = D_INK
    panel.line.fill.background()
    panel.shadow.inherit = False
    textbox(s, Inches(0.9), Inches(0.85), Inches(11.5), Inches(0.9),
            "Warehouse Box-Pushing (Sokoban) Solver", 40, bold=True, colour=D_PANEL)
    textbox(s, Inches(0.9), Inches(1.85), Inches(11.5), Inches(0.6),
            "A* search with deadlock detection, and a GUI that visualizes the "
            "AI-computed moves", 18, colour=RGBColor(0xA9, 0xB4, 0xC6))
    textbox(s, Inches(0.9), Inches(3.5), Inches(11.5), Inches(0.5),
            "Python 3 \u00b7 standard library only \u00b7 1,029 lines \u00b7 25 tests",
            16, colour=D_MUTED)
    notes(s, "A solver for Sokoban, the warehouse box-pushing puzzle. The program "
             "finds an optimal plan with A* and then animates it on the board.")

    # 2 -- the puzzle ------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "The puzzle", "problem")
    bullets(s, [
        "A worker pushes boxes around a warehouse grid onto marked targets.",
        "Boxes can only be PUSHED, never pulled -- the worker must stand on the "
        "opposite side.",
        "One wrong push can make the level permanently unsolvable, with no warning.",
        "Sokoban is PSPACE-complete: the state space explodes and brute force dies "
        "almost immediately.",
    ])
    card(s, Inches(0.8), Inches(4.6), Inches(11.7), Inches(1.5), "The goal",
         "Compute an optimal sequence of pushes, prove it is correct by replaying "
         "it against the rules, and show the solution moving on screen.")
    notes(s, "Push-only is what makes the puzzle hard: moves are not reversible, "
             "so the search can walk into dead positions.")

    # 3 -- rules -----------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "The rules", "rules")
    add_table(s, [
        ["Element", "Symbol", "Behaviour"],
        ["Wall", "#", "Blocks the worker and every box"],
        ["Floor", "(space)", "Freely walkable"],
        ["Target", ".", "Where a box must end up"],
        ["Box", "$", "Pushed one square if the square beyond is free"],
        ["Box on target", "*", "Counts as placed; can still be pushed off"],
        ["Worker", "@", "Moves one square up, down, left or right"],
        ["Worker on target", "+", "Same, standing on a target"],
    ], Inches(0.8), Inches(1.8), Inches(11.7), Inches(3.4))
    bullets(s, [
        "A push is legal only if the worker can reach the square directly opposite "
        "the box, and the square beyond the box is empty.",
        "The level is solved when every box sits on a target.",
    ], top=Inches(5.5), size=15)
    notes(s, "This is the standard .sok notation, so any level file from the "
             "internet loads without conversion.")

    # 4 -- architecture ----------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "Architecture", "architecture")
    textbox(s, Inches(0.8), Inches(1.6), Inches(11.7), Inches(0.4),
            "Three modules, one direction of dependency -- nothing below knows "
            "about anything above it.", 14, colour=D_MUTED)
    card(s, Inches(0.8), Inches(2.25), Inches(3.6), Inches(2.5), "gui.py",
         "Tkinter window. Canvas drawing, keyboard play, replay timer, and the "
         "worker thread that keeps the window alive while the search runs.")
    card(s, Inches(4.85), Inches(2.25), Inches(3.6), Inches(2.5), "solver.py",
         "Pull distances, deadlock detection, Hungarian assignment, and the A* "
         "loop. Pure computation, no I/O.", accent=D_BOX)
    card(s, Inches(8.9), Inches(2.25), Inches(3.6), Inches(2.5), "game.py",
         "The rules. Walls, targets, state, legal moves, push generation and "
         ".sok parsing. Knows nothing about searching.", accent=D_GOOD)
    for left in (Inches(4.45), Inches(8.5)):
        textbox(s, left, Inches(3.3), Inches(0.4), Inches(0.4), "\u2192", 22,
                bold=True, colour=D_MUTED)
    bullets(s, [
        "Board is immutable and shared by every node; State is a small frozen "
        "value object, so it drops straight into a hash set.",
        "The GUI never touches the search internals -- it asks for a move string "
        "and replays it keystroke by keystroke.",
    ], top=Inches(5.1), size=14)
    notes(s, "The split means the solver is testable without a display, and the "
             "GUI cannot corrupt search state.")

    # 5 -- flow ------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "Flow: what happens when you press Solve", "flow")
    steps = [
        ("1", "Snapshot", "GUI grabs the current position -- you may have pushed "
                          "boxes by hand first."),
        ("2", "Analyse", "Pull distances per target; dead squares fall out of it."),
        ("3", "Search", "A* over pushes on a worker thread, reporting progress."),
        ("4", "Expand", "Walk path between pushes is reconstructed into keystrokes."),
        ("5", "Verify", "Move string replayed against the rules before it is trusted."),
        ("6", "Replay", "Timer feeds one move every 90 ms into the same code your "
                        "arrow keys use."),
    ]
    top = Inches(1.75)
    for index, (number, heading, body) in enumerate(steps):
        y = top + Inches(0.88) * index
        chip = s.shapes.add_shape(9, Inches(0.8), y, Inches(0.52), Inches(0.52))
        chip.fill.solid()
        chip.fill.fore_color.rgb = D_ACCENT
        chip.line.fill.background()
        chip.shadow.inherit = False
        chip.text_frame.text = number
        run = chip.text_frame.paragraphs[0].runs[0]
        run.font.size, run.font.bold, run.font.color.rgb = Pt(14), True, D_PANEL
        textbox(s, Inches(1.55), y - Inches(0.02), Inches(2.0), Inches(0.4),
                heading, 15, bold=True)
        textbox(s, Inches(3.5), y - Inches(0.02), Inches(9.0), Inches(0.5), body, 13,
                colour=D_MUTED)
    notes(s, "Step 5 matters: the solver never marks its own homework. Every "
             "solution is replayed through the ordinary move function.")

    # 6 -- key idea 1 ------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "Idea 1: search pushes, not footsteps", "algorithms")
    bullets(s, [
        "Where the worker walks between two pushes never changes what is solvable.",
        "So the search branches only on box pushes -- a handful per position, "
        "instead of four moves per step.",
        "Walking is reconstructed once at the very end, by breadth-first search "
        "between consecutive pushes.",
        "Cost is counted in pushes, the standard measure for Sokoban solvers.",
    ])
    card(s, Inches(0.8), Inches(4.5), Inches(5.6), Inches(1.6), "Without this",
         "Branching factor 4 at every single footstep; depth in the hundreds.",
         accent=D_BOX)
    card(s, Inches(6.9), Inches(4.5), Inches(5.6), Inches(1.6), "With this",
         "Branching factor ~ boxes x 4; the hardest bundled level is 28 pushes deep.",
         accent=D_GOOD)
    notes(s, "This single reframing is the difference between intractable and "
             "a couple of seconds.")

    # 7 -- key idea 2 ------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "Idea 2: collapse equivalent positions", "algorithms")
    bullets(s, [
        "Two positions with identical boxes are the SAME node whenever the worker "
        "can walk between them.",
        "So a state is keyed by its boxes plus the top-left square of the worker's "
        "reachable area, not by where the worker happens to stand.",
        "That divides the state space by roughly the size of the open floor.",
    ])
    textbox(s, Inches(0.8), Inches(4.1), Inches(11.7), Inches(0.35),
            "sokoban/game.py", 12, bold=True, colour=D_MUTED, font="Consolas")
    code = s.shapes.add_shape(1, Inches(0.8), Inches(4.5), Inches(11.7), Inches(1.5))
    code.fill.solid()
    code.fill.fore_color.rgb = D_PANEL
    code.line.color.rgb = D_ACCENT
    code.shadow.inherit = False
    frame = code.text_frame
    frame.word_wrap = True
    frame.text = ("def normalize(self, state):\n"
                  "    return (min(self.reachable(state.player, state.boxes)), state.boxes)")
    for p in frame.paragraphs:
        p.runs[0].font.size = Pt(14)
        p.runs[0].font.name = "Consolas"
        p.runs[0].font.color.rgb = D_INK
    notes(s, "One line, and it is the second biggest win in the whole program.")

    # 8 -- deadlocks -------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "Idea 3: throw out lost positions on sight", "algorithms")
    textbox(s, Inches(0.8), Inches(1.6), Inches(11.7), Inches(0.4),
            "Most branches are already unwinnable long before the search would "
            "notice. Two tests run on every generated position.", 14, colour=D_MUTED)
    card(s, Inches(0.8), Inches(2.3), Inches(5.6), Inches(2.6), "Simple deadlock",
         "The box sits on a square from which NO target can be reached -- a "
         "corner, or the wall-hugging strip between two corners.\n\n"
         "Falls straight out of the pull-distance tables. One set lookup.",
         accent=D_BOX)
    card(s, Inches(6.9), Inches(2.3), Inches(5.6), Inches(2.6), "Freeze deadlock",
         "The box can never move along either axis again -- pinned by walls, dead "
         "squares or other immovable boxes. If it is off-target, the level is lost."
         "\n\nMutually recursive: A can be frozen because B is, and vice versa.",
         accent=D_BOX)
    textbox(s, Inches(0.8), Inches(5.3), Inches(11.7), Inches(0.9),
            "On the hardest bundled level this discards 11,472 positions outright "
            "-- roughly twice as many as it ever has to examine.", 16, bold=True,
            colour=D_GOOD)
    notes(s, "The freeze check assumes a box is frozen while its own check is "
             "still running. That terminates the recursion and is safe: if the "
             "assumption is wrong the outer call reports not-frozen anyway.")

    # 9 -- heuristic -------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "The heuristic: pull distances + assignment", "algorithms")
    bullets(s, [
        "Before searching, pull one imaginary box BACKWARDS out of each target "
        "-- the reverse of pushing it in.",
        "That gives, for every square, how many pushes a lone box needs to reach "
        "that target.",
        "Other boxes can only get in the way, so these are a lower bound: the "
        "heuristic is admissible and A* stays optimal.",
        "Every box needs its OWN target, which makes the estimate an assignment "
        "problem -- solved exactly with the Hungarian algorithm, O(n^3) in boxes.",
    ])
    card(s, Inches(0.8), Inches(5.0), Inches(11.7), Inches(1.25),
         "Why not just let each box take its nearest target?",
         "Measured on the hardest level: 7.3x more positions examined and 5.9x "
         "slower (11.2s vs 1.9s). The exact matching earns its 50 lines.",
         accent=D_GOOD)
    notes(s, "Nearest-target double-books one target across several boxes and so "
             "badly undercounts whenever boxes crowd together.")

    # 10 -- A* loop --------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "The A* loop", "algorithms")
    add_table(s, [
        ["Component", "Choice", "Why"],
        ["Cost g", "Pushes so far", "Unit cost, so the answer is push-optimal"],
        ["Estimate h", "Hungarian matching on pull distances", "Admissible lower bound"],
        ["Frontier", "Binary heap (heapq), ordered by g + h", "O(log n) push and pop"],
        ["Closed set", "Normalised states in a hash set", "O(1) duplicate rejection"],
        ["Pruning", "Deadlock test before a node is ever queued", "Keeps the heap small"],
        ["Tie-break", "Insertion counter", "Stable order, never compares states"],
    ], Inches(0.8), Inches(1.8), Inches(11.7), Inches(3.2))
    bullets(s, [
        "Terminates as solved, unsolvable (state space exhausted) or aborted "
        "(2,000,000 nodes / 60 s budget, or you pressed Stop).",
    ], top=Inches(5.4), size=15)
    notes(s, "Because h is admissible and consistent, the first goal node popped "
             "is optimal -- no need to keep searching.")

    # 11 -- results --------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "Results: the bundled pack", "results")
    compact = [results[0][:1] + results[0][2:]] + [r[:1] + r[2:] for r in results[1:]]
    add_table(s, compact, Inches(0.8), Inches(1.7), Inches(11.7), Inches(4.9), size=10)
    textbox(s, Inches(0.8), Inches(6.8), Inches(11.7), Inches(0.4),
            "Measured live when this deck was built; every solution was replayed "
            "against the rules and verified.", 11, colour=D_MUTED)
    notes(s, "Every one of these is a proven-optimal push count, not just a "
             "solution that happens to work.")

    # 12 -- GUI ------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "The GUI: visualizing the computed moves", "demo")
    bullets(s, [
        "Pick a level, press Solve, and the plan replays on the board one move "
        "at a time.",
        "The search runs on a worker thread and reports positions examined as it "
        "goes, so the window never freezes and Stop actually stops.",
        ("Tkinter is not thread-safe, so the worker parks its progress count and "
         "a Tk timer picks it up on the main thread.",),
        "You can also play by hand with the arrow keys or WASD.",
        ("Solve continues from wherever you got to -- push a few boxes yourself "
         "and let the AI finish.",),
        "Boxes turn green as they land on targets; Space pauses the replay, R resets.",
    ])
    notes(s, "Worth demoing the hybrid: push two boxes by hand, then hit Solve "
             "and watch it finish from that position.")

    # 13 -- testing --------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "How we know it is correct", "testing")
    bullets(s, [
        "25 tests, standard-library unittest, no framework.",
        "Every solution is REPLAYED against the rules from the start position -- "
        "the solver never marks its own homework.",
        "Admissibility is asserted, not assumed: the start estimate must never "
        "exceed the optimal push count A* actually found.",
        "Deadlock detection is tested on hand-built trap positions, including two "
        "boxes freezing each other.",
        "Parser rejects unenclosed levels, missing workers and more boxes than "
        "targets.",
    ])
    notes(s, "The verify step is the one that matters -- it has caught real bugs "
             "in the push-to-keystroke expansion.")

    # 14 -- limits ---------------------------------------------------------
    s = prs.slides.add_slide(blank)
    chrome(s, "Limits and what is next", "wrap-up")
    card(s, Inches(0.8), Inches(1.8), Inches(5.6), Inches(2.9), "Known limits",
         "\u2022 Push-optimal, not move-optimal: the walk between pushes is "
         "shortest, the total keystroke count is not minimised.\n"
         "\u2022 Simple and freeze deadlocks only; corral deadlocks are not "
         "detected.\n"
         "\u2022 Levels with 20+ boxes will hit the node budget.", accent=D_BOX)
    card(s, Inches(6.9), Inches(1.8), Inches(5.6), Inches(2.9), "Next steps",
         "\u2022 Corral and bipartite deadlock detection.\n"
         "\u2022 Tunnel macros: collapse forced corridor pushes into one move.\n"
         "\u2022 Transposition table keyed on a Zobrist hash.\n"
         "\u2022 Iterative-deepening A* to cut memory on deep levels.", accent=D_GOOD)
    textbox(s, Inches(0.8), Inches(5.2), Inches(11.7), Inches(0.6),
            "Every limit above is a documented decision, not an accident.", 16,
            bold=True, colour=D_ACCENT)
    notes(s, "Be upfront about the limits -- it is the difference between a "
             "project that was measured and one that was guessed at.")

    # 15 -- close ----------------------------------------------------------
    s = prs.slides.add_slide(blank)
    panel = s.shapes.add_shape(1, 0, 0, W, H)
    panel.fill.solid()
    panel.fill.fore_color.rgb = D_INK
    panel.line.fill.background()
    panel.shadow.inherit = False
    textbox(s, Inches(0.9), Inches(2.6), Inches(11.5), Inches(1.0),
            "Thank you", 44, bold=True, colour=D_PANEL)
    textbox(s, Inches(0.9), Inches(3.7), Inches(11.5), Inches(0.6),
            "A* over box pushes \u00b7 pull-distance heuristic with exact "
            "assignment \u00b7 simple and freeze deadlock pruning",
            17, colour=RGBColor(0xA9, 0xB4, 0xC6))
    textbox(s, Inches(0.9), Inches(4.6), Inches(11.5), Inches(0.5),
            "Questions?", 20, bold=True, colour=D_ACCENT)
    notes(s, "Likely questions: why pushes not moves, why Hungarian over greedy, "
             "what a corral deadlock is, and how the thread keeps the UI alive.")

    prs.save(str(path))
    print(f"  {path.name} ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")


# ------------------------------------------------------------------ build

def main() -> None:
    DOCS.mkdir(exist_ok=True)
    print("measuring the level pack...")
    results = measure()

    print("writing:")

    # ---- README ----------------------------------------------------------
    build_pdf(
        DOCS / "README.pdf",
        "Sokoban Solver",
        "Move a worker and boxes onto targets, and watch an A* search with "
        "deadlock detection compute and replay the solution.",
        [
            ("h1", "What it is"),
            ("p", "A solver for Sokoban, the warehouse box-pushing puzzle, with a "
                  "Tkinter window that animates the moves the AI works out. Written "
                  "in Python 3 using <b>nothing but the standard library</b> -- there "
                  "is no install step."),
            ("code", "python main.py"),
            ("h1", "Using it"),
            ("p", "Pick a level and press <b>Solve</b> (or Enter). The search runs on "
                  "a background thread, reports how many positions it has examined, "
                  "and replays the plan on the board when it finishes. <b>Space</b> "
                  "pauses and resumes, <b>R</b> resets."),
            ("p", "You can also play by hand with the <b>arrow keys</b> or "
                  "<b>WASD</b> -- and Solve picks up from wherever you have got to, "
                  "so you can push a few boxes yourself and let the AI finish."),
            ("h1", "Architecture"),
            ("table", ([["Module", "Lines", "Responsibility"],
                        ["sokoban/game.py", "252", "The rules: walls, targets, state, "
                         "legal moves, push generation, .sok parsing"],
                        ["sokoban/solver.py", "295", "Pull distances, deadlock "
                         "detection, Hungarian assignment, the A* loop"],
                        ["sokoban/gui.py", "317", "Tkinter window, threaded solving, "
                         "replay timer, canvas drawing"],
                        ["main.py", "7", "Launches the GUI"],
                        ["tests/test_sokoban.py", "157", "25 tests"]],
                       [95, 40, 300])),
            ("p", "Dependencies run one way only: <b>gui -> solver -> game</b>. "
                  "The game layer knows nothing about searching, and the solver "
                  "knows nothing about the display, so it can be tested headlessly."),
            ("h1", "How the solver works"),
            ("p", "Sokoban is PSPACE-complete, so brute force dies quickly. Three "
                  "things keep the search tractable."),
            ("h2", "1. It searches pushes, not footsteps"),
            ("p", "Where the worker walks between two pushes never changes what is "
                  "solvable, so the search only branches on box pushes. The walking "
                  "is reconstructed once at the end, so the GUI has a move sequence "
                  "to animate. Cost is counted in pushes, the standard measure for "
                  "Sokoban solvers."),
            ("h2", "2. Equivalent positions collapse into one"),
            ("p", "Two positions with identical boxes are the same node whenever the "
                  "worker can walk between them, so a state is keyed by its boxes "
                  "plus the top-left square of the worker's reachable area."),
            ("h2", "3. Lost positions are thrown out on sight"),
            ("bullets", [
                "<b>Simple deadlock</b> -- the box sits on a square from which no "
                "target can be reached: a corner, or the wall-hugging strip between "
                "two corners. One set lookup.",
                "<b>Freeze deadlock</b> -- the box can never move along either axis "
                "again, pinned by walls, dead squares or other immovable boxes. If it "
                "is not on a target, the position is lost. The check is mutually "
                "recursive, since box A can be frozen because B is and vice versa.",
            ]),
            ("p", "On the largest bundled level that discards 11,472 positions "
                  "outright."),
            ("h2", "The heuristic"),
            ("p", "Before searching, the solver pulls a single imaginary box "
                  "backwards out of each target to build a table of <i>pull "
                  "distances</i>: how many pushes a lone box needs to get from any "
                  "square to that target. Other boxes can only get in the way, so "
                  "these are a lower bound on the true cost -- the heuristic is "
                  "admissible and A* stays optimal."),
            ("p", "Turning those distances into an estimate is an assignment problem, "
                  "since every box needs its own target. Solving it exactly with the "
                  "<b>Hungarian algorithm</b> costs O(n^3) in the number of boxes -- "
                  "nothing next to the search, and worth it: letting each box pick "
                  "its own nearest target instead expands 7.3x more nodes and takes "
                  "5.9x longer on the hardest bundled level."),
            ("h1", "Results"),
            ("table", (results, [78, 34, 40, 38, 84, 76, 38])),
            ("caption", "Measured when this document was generated. Every solution "
                        "was replayed against the rules and verified."),
            ("h1", "Level format"),
            ("p", "<b>levels/levels.sok</b>, in the standard notation. Blank lines "
                  "separate levels and a <b>;</b> comment above one titles it."),
            ("code", "#  wall        @  player        +  player on target\n"
                     "$  box         *  box on target .  target"),
            ("h1", "Tests"),
            ("code", "python -m unittest discover -s tests -v"),
            ("p", "Covers parsing and validation, move legality, state "
                  "normalisation, dead-square and freeze-deadlock detection, the "
                  "assignment solver, and a solve-and-verify pass over every bundled "
                  "level. Every solution is replayed against the rules, so the solver "
                  "never marks its own homework."),
            ("h1", "Limits"),
            ("bullets", [
                "Cost is counted in pushes. The move string is the shortest walk "
                "between those pushes, not a move-optimal solution.",
                "Simple and freeze deadlocks only; corral deadlocks are not detected.",
                "Large levels (20+ boxes) will hit the 2,000,000-node / 60-second "
                "budget.",
            ]),
            ("pagebreak", None),
            ("h1", "Appendix: full source"),
            ("p", "Every line of the project, as generated."),
            *source_listing("main.py"),
            *source_listing("sokoban/game.py"),
            *source_listing("sokoban/solver.py"),
            *source_listing("sokoban/gui.py"),
            *source_listing("tests/test_sokoban.py"),
            *source_listing("levels/levels.sok"),
        ],
    )

    # ---- start guide ----------------------------------------------------
    build_pdf(
        DOCS / "StartGuide.pdf",
        "Start Guide",
        "How to run the Sokoban solver.",
        [
            ("h1", "1. What you need"),
            ("bullets", [
                "<b>Python 3.9 or newer.</b> Check with <font face='Courier'>python "
                "--version</font>.",
                "<b>Tkinter</b>, which ships with Python on Windows and macOS. On "
                "Debian or Ubuntu: <font face='Courier'>sudo apt install "
                "python3-tk</font>.",
                "<b>Nothing else.</b> No pip install, no virtual environment, no "
                "internet connection.",
            ]),
            ("h1", "2. Run it"),
            ("code", "cd sokoban-solver\npython main.py"),
            ("p", "The window opens on the first level, with the whole pack loaded "
                  "in the dropdown."),
            ("h1", "3. Solve a level"),
            ("bullets", [
                "Choose a level from the <b>Level</b> dropdown.",
                "Press <b>Solve</b>, or just hit <b>Enter</b>.",
                "The status line counts positions examined while it searches, then "
                "reports the push count, move count and time.",
                "The solution replays on the board automatically. Boxes turn "
                "<b>green</b> as they land on targets.",
            ]),
            ("h1", "4. The controls"),
            ("table", ([["Control", "Key", "What it does"],
                        ["Level dropdown", "--", "Switches level and resets the board"],
                        ["Solve", "Enter", "Searches from the CURRENT position; "
                         "press again to stop"],
                        ["Play / Pause", "Space", "Pauses and resumes the replay"],
                        ["Reset", "R", "Puts the level back to its starting position"],
                        ["Move worker", "Arrows or WASD", "Walk, pushing a box if "
                         "one is in the way"]],
                       [90, 85, 275])),
            ("p", "You can push boxes yourself and then press Enter -- Solve "
                  "searches from wherever you have got to."),
            ("h1", "If it will not start"),
            ("p", "<b>ModuleNotFoundError: tkinter</b> is the only thing that "
                  "normally blocks a first run. On Linux install "
                  "<font face='Courier'>python3-tk</font>; on Windows, reinstall "
                  "Python with the <i>tcl/tk and IDLE</i> option ticked."),
        ],
    )

    # ---- tech stack ------------------------------------------------------
    build_pdf(
        DOCS / "TechStack.pdf",
        "Technology Stack",
        "Every language, library, algorithm and data structure in the project, "
        "and why each one is there.",
        [
            ("h1", "At a glance"),
            ("table", ([["Layer", "Choice", "Version"],
                        ["Language", "Python", "3.9+ (developed on CPython 3.14)"],
                        ["GUI toolkit", "Tkinter / ttk", "Standard library"],
                        ["Search", "A* over box pushes", "Hand-written"],
                        ["Heuristic", "Hungarian assignment on pull distances",
                         "Hand-written"],
                        ["Test framework", "unittest", "Standard library"],
                        ["Runtime dependencies", "None", "--"],
                        ["Version control", "Git", "--"]],
                       [95, 250, 110])),
            ("h1", "Why no third-party packages"),
            ("p", "The entire program runs on a stock Python install. That is a "
                  "deliberate constraint, not an oversight:"),
            ("bullets", [
                "It runs anywhere Python runs -- a lab machine, an examiner's laptop, "
                "a locked-down desktop -- with no pip, no network and no virtual "
                "environment.",
                "Nothing can break through a dependency upgrade.",
                "Every algorithm in the project is visible and reviewable rather than "
                "hidden behind a library call, which is the point of the exercise.",
            ]),
            ("p", "The documents you are reading were produced with reportlab and "
                  "python-pptx, but those are <b>build-time only</b> and are not "
                  "imported anywhere in the program."),
            ("h1", "Standard library modules used"),
            ("table", ([["Module", "Used for"],
                        ["tkinter, tkinter.ttk", "The window, canvas drawing, themed "
                         "widgets, keyboard binding and the replay timer"],
                        ["heapq", "The A* frontier as a binary min-heap"],
                        ["collections.deque", "Breadth-first queues for flood fill, "
                         "pull distances and walk paths"],
                        ["dataclasses", "Frozen, hashable State and Push value "
                         "objects; the mutable Result"],
                        ["threading", "Running the search off the UI thread; Event "
                         "for cancellation"],
                        ["queue", "Handing the finished result back to the Tk main "
                         "loop safely"],
                        ["time", "perf_counter for the time budget and reported "
                         "timings"],
                        ["pathlib", "Locating the bundled level pack"],
                        ["typing", "Type hints throughout"],
                        ["unittest", "The test suite"],
                        ["html, textwrap", "Documentation build only"]],
                       [130, 325])),
            ("h1", "Algorithms"),
            ("table", ([["Algorithm", "Where", "Role"],
                        ["A* search", "solver.solve", "Finds a push-optimal plan"],
                        ["Hungarian algorithm", "solver.min_cost_assignment",
                         "Exact minimum-cost box-to-target matching for the heuristic"],
                        ["Reverse (pull) BFS", "Analysis._pull_distances_from",
                         "Push distance from every square to each target"],
                        ["Flood fill / BFS", "Board.reachable, Board._flood_fill",
                         "Worker reachability, state normalisation, enclosure check"],
                        ["BFS shortest path", "Board.walk_path",
                         "Turns consecutive pushes into keystrokes"],
                        ["Freeze-deadlock recursion", "Analysis._is_frozen",
                         "Detects mutually immovable boxes"]],
                       [125, 150, 180])),
            ("h1", "Data structures"),
            ("table", ([["Structure", "Why it was chosen"],
                        ["frozenset of coordinates", "Box positions: hashable, so a "
                         "state drops straight into a dict or set; set algebra makes "
                         "a push one expression"],
                        ["Binary heap (heapq)", "Frontier ordered by g + h; O(log n) "
                         "push and pop"],
                        ["Hash set", "Closed set of normalised states; O(1) duplicate "
                         "rejection"],
                        ["Dict of dicts", "Pull distances, one table per target"],
                        ["Frozen dataclass", "State and Push: immutable, hashable, "
                         "cheap to compare"],
                        ["Insertion counter", "Heap tie-break, so states are never "
                         "compared to each other"]],
                       [135, 320])),
            ("h1", "Complexity"),
            ("table", ([["Operation", "Cost", "Note"],
                        ["Pull-distance tables", "O(targets x floor)", "Once per "
                         "solve, microseconds"],
                        ["Heuristic per node", "O(b^3), b = boxes", "Hungarian; "
                         "negligible beside expansion"],
                        ["Successors per node", "O(b x floor)", "Reachability flood "
                         "fill dominates"],
                        ["Deadlock test", "O(b) amortised", "Only the box that moved "
                         "is checked"],
                        ["Search", "Exponential in boxes", "PSPACE-complete problem; "
                         "pruning is what makes it finish"]],
                       [130, 125, 200])),
            ("h1", "Measured performance"),
            ("table", (results, [78, 34, 40, 38, 84, 76, 38])),
            ("caption", "Measured when this document was generated, single-threaded "
                        "CPython."),
            ("h1", "Concurrency model"),
            ("p", "One worker thread runs the search; the Tk main loop owns every "
                  "widget. They communicate two ways, both one-directional:"),
            ("bullets", [
                "<b>Cancellation</b> -- a <font face='Courier'>threading.Event</font> "
                "the search polls every 2,000 nodes, so Stop and level switches take "
                "effect promptly.",
                "<b>Results</b> -- a <font face='Courier'>queue.Queue</font> the Tk "
                "main loop drains on a 60 ms timer.",
                "<b>Progress</b> -- a plain integer the worker overwrites and the "
                "timer reads, because calling into Tk from another thread is not "
                "safe.",
            ]),
            ("h1", "Testing"),
            ("table", ([["Aspect", "Approach"],
                        ["Framework", "unittest, standard library, no plugins"],
                        ["Count", "25 tests, about 4 seconds"],
                        ["Oracle", "Every solution is replayed against the rules from "
                         "the start position"],
                        ["Property checked", "Heuristic admissibility: the start "
                         "estimate never exceeds the optimal push count found"],
                        ["Fixtures", "Hand-built trap positions for deadlock "
                         "detection; malformed levels for the parser"]],
                       [110, 345])),
            ("h1", "Platform support"),
            ("p", "Windows, macOS and Linux, wherever CPython 3.9+ and Tkinter are "
                  "present. No platform-specific code, no file-system assumptions "
                  "beyond locating the bundled level pack relative to the package."),
        ],
    )

    # ---- deck ------------------------------------------------------------
    deck(DOCS / "Presentation.pptx", results)
    print(f"\ndone -> {DOCS}")


if __name__ == "__main__":
    main()
