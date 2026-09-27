"""
Read the Checkers Arena endgame tablebase: perfect play for every American
checkers (English draughts) position with four pieces or fewer.

Standard library only — no numpy, no install. Python 3.8+.

    from checkers_endgame import Tablebase, Board

    tb = Tablebase("endgame4.bin.gz")
    b  = Board.from_code("3b6b2R17rr")      # or Board.from_rows([...])
    print(tb.probe(b))                       # Result(outcome='win', plies=11, moves=6)
    print(tb.best_move(b))                   # ((4, 5), (3, 4))

Or from the shell:

    python checkers_endgame.py 3b6b2R17rr
    python checkers_endgame.py --line 3b6b2R17rr      # play the whole win out

WHY THIS FILE EXISTS, AND WHY IT REIMPLEMENTS THE RULES
The tablebase is a flat array of bytes; without the indexing scheme it is
noise. This module is the scheme, written out independently of the JavaScript
the table was generated with, so the dataset stands on its own — and so that
anyone checking our work has a second implementation to check it against. The
move generator is here for the same reason: looking a position up is useful,
playing the win out is what shows the data is real.

The position codec (`Board.from_code`) is the same one the analysis board at
https://checkersarena.io/checkers-solver/ puts in its URL, so any position you
can see there can be pasted here.
"""

from __future__ import annotations

import gzip
import sys
from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

__all__ = ["Board", "Tablebase", "Result", "Move"]

SIZE = 8
MAX_PIECES = 4

RED, BLACK = "red", "black"

# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

# The 32 playable squares: dark = (row + col) odd, ordered row by row.
# Row 0 is the top of the board (Black's back row); row 7 is the bottom
# (Red's back row). Red moves toward row 0.
SQUARES: List[Tuple[int, int]] = [
    (r, c) for r in range(SIZE) for c in range(SIZE) if (r + c) % 2 == 1
]
SQUARE_INDEX: Dict[Tuple[int, int], int] = {rc: i for i, rc in enumerate(SQUARES)}

# A red man can never stand on row 0 and a black man never on row 7: arriving
# there crowns it. Those positions do not exist, so they are given no slots and
# men are indexed over 28 squares rather than 32.
DOMAIN = {
    "red_man": [i for i, (r, _) in enumerate(SQUARES) if r != 0],
    "black_man": [i for i, (r, _) in enumerate(SQUARES) if r != SIZE - 1],
    "king": list(range(len(SQUARES))),
}
DOMAIN_POS = {
    name: {sq: k for k, sq in enumerate(squares)} for name, squares in DOMAIN.items()
}

# ---------------------------------------------------------------------------
# byte encoding, one byte per slot
# ---------------------------------------------------------------------------

UNUSED = 0        # no legal position maps here (see FORMAT.md, "gaps")
DRAW = 1
WIN_BASE = 2      # 2..127   -> red (side to move) wins in (value - 2) plies
LOSS_BASE = 128   # 128..255 -> side to move loses in (value - 128) plies


@dataclass(frozen=True)
class Result:
    """What the table says about a position, from the side to move's view."""

    outcome: str          # "win", "loss" or "draw"
    plies: int            # half-moves until the game ends; 0 for a draw
    moves: int            # whole moves the winner still has to play

    def __str__(self) -> str:
        if self.outcome == "draw":
            return "draw with perfect play"
        who = "side to move wins" if self.outcome == "win" else "side to move loses"
        return f"{who} in {self.moves} moves ({self.plies} plies)"


def moves_to_end(plies: int) -> int:
    """Plies to whole moves. A game ends when the loser has nothing left, so a
    win always takes an odd number of plies and a loss an even number; the
    conversion is exact, never rounded."""
    return (plies + 1) // 2 if plies % 2 else plies // 2


Move = Tuple[Tuple[int, int], Tuple[int, int]]

# ---------------------------------------------------------------------------
# the board
# ---------------------------------------------------------------------------


class Board:
    """An 8x8 American checkers position plus the side to move.

    Squares hold None or one of "r" (red man), "R" (red king), "b", "B".
    """

    __slots__ = ("cells", "turn")

    def __init__(self, cells: Optional[List[List[Optional[str]]]] = None,
                 turn: str = RED):
        self.cells = cells if cells is not None else [
            [None] * SIZE for _ in range(SIZE)
        ]
        self.turn = turn

    # -- construction -------------------------------------------------------

    @classmethod
    def from_rows(cls, rows: Sequence[str], turn: str = RED) -> "Board":
        """Eight strings of eight characters, top row first. Use '.' or ' ' for
        an empty square:

            Board.from_rows([
                "........", "...b....", "........", "........",
                "........", "..R.....", "........", "........",
            ], turn="red")
        """
        if len(rows) != SIZE:
            raise ValueError(f"expected {SIZE} rows, got {len(rows)}")
        board = cls(turn=turn)
        for r, row in enumerate(rows):
            if len(row) != SIZE:
                raise ValueError(f"row {r} has {len(row)} squares, expected {SIZE}")
            for c, ch in enumerate(row):
                if ch in ".  _":
                    continue
                if ch not in "rRbB":
                    raise ValueError(f"unknown piece {ch!r} at row {r}, column {c}")
                board.cells[r][c] = ch
        return board

    @classmethod
    def from_code(cls, code: str) -> "Board":
        """Parse the position codec used in checkersarena.io URLs (?p=...).

        The 32 dark squares in board order, where a letter is a piece and a
        number is a run of empty squares, then one final character for the side
        to move. The starting position is 26 characters long.
        """
        code = code.strip()
        if len(code) < 2:
            raise ValueError("position code too short")
        turn_char, body = code[-1], code[:-1]
        if turn_char not in "rb":
            raise ValueError("last character must be 'r' or 'b' (side to move)")
        board = cls(turn=RED if turn_char == "r" else BLACK)
        at, i = 0, 0
        while i < len(body):
            ch = body[i]
            if ch.isdigit():
                run = 0
                while i < len(body) and body[i].isdigit():
                    run = run * 10 + int(body[i])
                    i += 1
                if run == 0:
                    raise ValueError("a run of zero empty squares")
                at += run
                continue
            if ch not in "rRbB":
                raise ValueError(f"unknown piece letter {ch!r}")
            if at >= len(SQUARES):
                raise ValueError("more squares than the board has")
            r, c = SQUARES[at]
            board.cells[r][c] = ch
            at += 1
            i += 1
        if at != len(SQUARES):
            raise ValueError("the code does not describe all 32 dark squares")
        return board

    # -- inspection ---------------------------------------------------------

    def pieces(self) -> Iterator[Tuple[int, int, str]]:
        for r in range(SIZE):
            for c in range(SIZE):
                p = self.cells[r][c]
                if p is not None:
                    yield r, c, p

    def count(self) -> int:
        return sum(1 for _ in self.pieces())

    def copy(self) -> "Board":
        return Board([row[:] for row in self.cells], self.turn)

    def rotated(self) -> "Board":
        """Turn the board 180 degrees and swap the colours — the transform that
        maps the game exactly onto itself, and the reason the file stores only
        red-to-move positions. A rotated red piece moves toward row 7 just as a
        black piece does, and the two crowning rows map onto each other."""
        out = Board(turn=BLACK if self.turn == RED else RED)
        swap = {"r": "b", "R": "B", "b": "r", "B": "R"}
        for r, c, p in self.pieces():
            out.cells[SIZE - 1 - r][SIZE - 1 - c] = swap[p]
        return out

    def __str__(self) -> str:
        lines = []
        for r in range(SIZE):
            row = "".join(self.cells[r][c] or "." for c in range(SIZE))
            lines.append(f"{SIZE - r} {row}")
        lines.append("  abcdefgh")
        lines.append(f"  {self.turn} to move")
        return "\n".join(lines)

    # -- rules (American checkers / English draughts) -----------------------

    @staticmethod
    def _directions(piece: str) -> List[Tuple[int, int]]:
        if piece in "RB":
            return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        # a red man moves toward row 0, a black man toward row 7
        return [(-1, -1), (-1, 1)] if piece == "r" else [(1, -1), (1, 1)]

    def _owner(self, piece: str) -> str:
        return RED if piece in "rR" else BLACK

    def _jumps_from(self, r: int, c: int) -> List[Tuple[int, int]]:
        piece = self.cells[r][c]
        out = []
        for dr, dc in self._directions(piece):
            mr, mc, tr, tc = r + dr, c + dc, r + 2 * dr, c + 2 * dc
            if not (0 <= tr < SIZE and 0 <= tc < SIZE):
                continue
            mid = self.cells[mr][mc]
            if mid is None or self._owner(mid) == self._owner(piece):
                continue
            if self.cells[tr][tc] is None:
                out.append((tr, tc))
        return out

    def legal_moves(self) -> List[Move]:
        """Every legal move for the side to move, as (from, to) pairs. Captures
        are compulsory, so when any jump exists only jumps are returned. A move
        here is one HOP: a multi-jump is several hops, which `apply` reports so
        a caller can continue the chain."""
        jumps, steps = [], []
        for r, c, p in self.pieces():
            if self._owner(p) != self.turn:
                continue
            for tr, tc in self._jumps_from(r, c):
                jumps.append(((r, c), (tr, tc)))
            if not jumps:
                for dr, dc in self._directions(p):
                    tr, tc = r + dr, c + dc
                    if 0 <= tr < SIZE and 0 <= tc < SIZE and self.cells[tr][tc] is None:
                        steps.append(((r, c), (tr, tc)))
        return jumps if jumps else steps

    def apply(self, move: Move) -> "Board":
        """Play one hop and return the new position. When the hop was a capture
        and the same piece can jump again without having just been crowned, the
        turn does NOT pass — the chain must be finished."""
        (fr, fc), (tr, tc) = move
        out = self.copy()
        piece = out.cells[fr][fc]
        if piece is None:
            raise ValueError(f"no piece on {fr},{fc}")
        out.cells[fr][fc] = None
        captured = abs(tr - fr) == 2
        if captured:
            out.cells[(fr + tr) // 2][(fc + tc) // 2] = None
        crowned = False
        if piece == "r" and tr == 0:
            piece, crowned = "R", True
        elif piece == "b" and tr == SIZE - 1:
            piece, crowned = "B", True
        out.cells[tr][tc] = piece
        # Crowning ends the turn even mid-chain: a freshly made king does not
        # keep jumping on the same move.
        if captured and not crowned and out._jumps_from(tr, tc):
            out.turn = self.turn
        else:
            out.turn = BLACK if self.turn == RED else RED
        return out

    def turn_moves(self) -> List[Tuple[Move, "Board"]]:
        """Complete turns: every whole move including finished capture chains,
        each with the resulting position. The reported move is the first hop
        and the square the piece ended on."""
        out: List[Tuple[Move, "Board"]] = []
        for first in self.legal_moves():
            stack = [(first, self.apply(first))]
            while stack:
                mv, pos = stack.pop()
                if pos.turn == self.turn:                   # chain continues
                    for nxt in pos.legal_moves():
                        stack.append(((mv[0], nxt[1]), pos.apply(nxt)))
                else:
                    out.append((mv, pos))
        return out


# ---------------------------------------------------------------------------
# the index: position -> slot
# ---------------------------------------------------------------------------


def _signatures() -> List[Tuple[int, int, int, int]]:
    """Material signatures (red men, red kings, black men, black kings) in the
    exact order the blocks are laid out in the file. A side with no pieces has
    already lost and needs no entry."""
    sigs = []
    for rm in range(MAX_PIECES + 1):
        for rk in range(MAX_PIECES + 1 - rm):
            for bm in range(MAX_PIECES + 1 - rm - rk):
                for bk in range(MAX_PIECES + 1 - rm - rk - bm):
                    if rm + rk == 0 or bm + bk == 0:
                        continue
                    sigs.append((rm, rk, bm, bk))
    return sigs


SIGNATURES = _signatures()

_N_MAN = len(DOMAIN["red_man"])     # 28
_N_KING = len(DOMAIN["king"])       # 32


def _signature_size(sig: Tuple[int, int, int, int]) -> int:
    rm, rk, bm, bk = sig
    return comb(_N_MAN, rm) * comb(_N_KING, rk) * comb(_N_MAN, bm) * comb(_N_KING, bk)


def _offsets() -> Tuple[Dict[Tuple[int, int, int, int], int], int]:
    off, total = {}, 0
    for sig in SIGNATURES:
        off[sig] = total
        total += _signature_size(sig)
    return off, total


OFFSET, TOTAL_SLOTS = _offsets()


def _rank_subset(sorted_positions: Sequence[int]) -> int:
    """Combinatorial number system: the rank of a sorted k-subset of {0..n-1}
    is the sum of C(a_i, i+1). It is a bijection onto 0..C(n,k)-1, so every
    position gets exactly one slot and every slot exactly one position."""
    return sum(comb(a, i + 1) for i, a in enumerate(sorted_positions))


def _classify(board: Board):
    """Split a board into per-class sorted domain positions, or None when the
    position has no slot at all: too many pieces, one side empty, or a man
    standing where a man cannot stand."""
    groups = {"rm": [], "rk": [], "bm": [], "bk": []}
    for r, c, p in board.pieces():
        sq = SQUARE_INDEX.get((r, c))
        if sq is None:
            return None                              # a piece on a light square
        if p == "r":
            k = DOMAIN_POS["red_man"].get(sq)
            if k is None:
                return None                          # red man on its crowning row
            groups["rm"].append(k)
        elif p == "R":
            groups["rk"].append(DOMAIN_POS["king"][sq])
        elif p == "b":
            k = DOMAIN_POS["black_man"].get(sq)
            if k is None:
                return None
            groups["bm"].append(k)
        else:
            groups["bk"].append(DOMAIN_POS["king"][sq])
    total = sum(len(v) for v in groups.values())
    if total == 0 or total > MAX_PIECES:
        return None
    if not (groups["rm"] or groups["rk"]) or not (groups["bm"] or groups["bk"]):
        return None
    for v in groups.values():
        v.sort()
    return groups


def slot_of(board: Board) -> int:
    """The slot for a RED-to-move board, or -1 if the position is not stored.
    Callers should use Tablebase.probe, which handles black to move."""
    cls = _classify(board)
    if cls is None:
        return -1
    sig = (len(cls["rm"]), len(cls["rk"]), len(cls["bm"]), len(cls["bk"]))
    base = OFFSET.get(sig)
    if base is None:
        return -1
    n_rk = comb(_N_KING, sig[1])
    n_bm = comb(_N_MAN, sig[2])
    n_bk = comb(_N_KING, sig[3])
    idx = ((_rank_subset(cls["rm"]) * n_rk + _rank_subset(cls["rk"])) * n_bm
           + _rank_subset(cls["bm"])) * n_bk + _rank_subset(cls["bk"])
    return base + idx


# ---------------------------------------------------------------------------
# the table
# ---------------------------------------------------------------------------


class Tablebase:
    """The byte array, with lookups on top of it."""

    def __init__(self, path: str = "endgame4.bin.gz"):
        opener = gzip.open if path.endswith(".gz") else open
        with opener(path, "rb") as fh:
            self.data = fh.read()
        if len(self.data) != TOTAL_SLOTS:
            raise ValueError(
                f"{path} holds {len(self.data)} bytes, expected {TOTAL_SLOTS}. "
                "A truncated table would answer confidently about the wrong "
                "position, so this is refused rather than tolerated."
            )

    def __len__(self) -> int:
        return len(self.data)

    def probe(self, board: Board) -> Optional[Result]:
        """What happens with perfect play, from the side to move's point of
        view. None when the position is outside the table (more than four
        pieces, or one side already has none)."""
        query = board if board.turn == RED else board.rotated()
        slot = slot_of(query)
        if slot < 0:
            return None
        value = self.data[slot]
        if value == UNUSED:
            return None
        if value == DRAW:
            return Result("draw", 0, 0)
        if value < LOSS_BASE:
            plies = value - WIN_BASE
            return Result("win", plies, moves_to_end(plies))
        plies = value - LOSS_BASE
        return Result("loss", plies, moves_to_end(plies))

    def best_move(self, board: Board) -> Optional[Move]:
        """The move that keeps a win and finishes it fastest, or holds a draw,
        or loses as slowly as possible. None when the position is not in the
        table or the side to move has no legal move at all.

        Distances are what make this work. With only win/loss/draw the table
        could avoid throwing a win away but would have no reason to ever
        finish, and would shuffle forever."""
        options = board.turn_moves()
        if not options:
            return None
        here = self.probe(board)
        best_move, best_key = None, None
        for move, after in options:
            if not any(True for _ in after.pieces()):
                return move
            result = self.probe(after)
            if result is None:
                continue
            # `after` is the opponent to move, so their loss is our win
            if result.outcome == "loss":
                key = (0, result.plies)        # we win: finish it soonest
            elif result.outcome == "draw":
                key = (1, 0)
            else:
                key = (2, -result.plies)       # we lose: drag it out
            if best_key is None or key < best_key:
                best_move, best_key = move, key
        if best_move is None and here is not None:
            return options[0][0]
        return best_move

    def line(self, board: Board, limit: int = 200) -> List[Move]:
        """Play the position out with best play from both sides."""
        out, pos = [], board.copy()
        for _ in range(limit):
            if self.probe(pos) is None and pos.count() > MAX_PIECES:
                break
            move = self.best_move(pos)
            if move is None:
                break
            out.append(move)
            after = pos.apply(move)
            while after.turn == pos.turn:                     # finish the chain
                nxt = after.legal_moves()
                if not nxt:
                    break
                after = after.apply(nxt[0])
            pos = after
        return out


# ---------------------------------------------------------------------------
# notation helpers and the command line
# ---------------------------------------------------------------------------


def square_name(rc: Tuple[int, int]) -> str:
    """Board coordinates as they appear on checkersarena.io: files a-h across
    the bottom, ranks 1-8 up the side, with rank 1 on Red's side."""
    r, c = rc
    return f"{'abcdefgh'[c]}{SIZE - r}"


def move_name(move: Move) -> str:
    return f"{square_name(move[0])}-{square_name(move[1])}"


def _main(argv: List[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    if not args:
        print(__doc__.strip())
        return 0
    try:
        board = Board.from_code(args[0])
    except ValueError as exc:
        print(f"could not read that position: {exc}", file=sys.stderr)
        return 2
    path = args[1] if len(args) > 1 else "endgame4.bin.gz"
    try:
        tb = Tablebase(path)
    except FileNotFoundError:
        print(f"tablebase not found at {path}", file=sys.stderr)
        return 2
    print(board)
    print()
    result = tb.probe(board)
    if result is None:
        print("not in the table (more than four pieces, or one side has none)")
        return 1
    print(result)
    move = tb.best_move(board)
    if move:
        print(f"best move: {move_name(move)}")
    if "--line" in flags:
        moves = tb.line(board)
        print(f"perfect play ({len(moves)} plies, {moves_to_end(len(moves))} moves):")
        print("  " + "  ".join(move_name(m) for m in moves))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
