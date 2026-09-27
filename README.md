# Checkers endgame tablebase — every position with four pieces or fewer, solved

**6,408,836 American checkers (English draughts) positions, each with an exact
result and an exact distance to the end.** Not an evaluation, not a search:
won, lost or drawn, and in how many moves. One 1.8 MB file, a reader in one
Python module, no dependencies and no service to call.

| | |
|---|---|
| Positions | **6,408,836** |
| Won / lost / drawn | 2,675,270 / 2,004,797 / 1,728,769 |
| Longest forced win | **109 plies — 55 moves** |
| File | 1.82 MB gzipped, 7.11 MB raw, one byte per slot |
| Rules | American checkers / English draughts, 8×8, no flying kings |
| Licence | [CC BY 4.0](LICENSE) — free to use, attribution required |

Play any of it in the browser at
**[checkersarena.io/checkers-endgame/](https://checkersarena.io/checkers-endgame/)**.

## Why this exists

Checkers was solved in 2007 by the Chinook team, who proved that perfect play
by both sides is a draw. That proof rests on enormous endgame databases — but
those are not something you can download, open and read this afternoon.

Meanwhile every free checkers "solver" on the web is a search engine with a
time budget. Search is at its worst exactly where this table is exact: in an
ending with a handful of pieces, where the win may be fifty moves away and
every move looks the same. The longest win here takes **109 plies**. No
time-limited search will ever find it.

So: the small end of the game, solved completely, in a form you can actually
use.

## Quick start

```bash
python checkers_endgame.py 2bb8r11r7r
```

```
8 .....b.b
7 ........
6 ........
5 r.......
4 ........
3 ........
2 .r......
1 ........
  abcdefgh
  red to move

side to move wins in 55 moves (109 plies)
best move: a5-b6
```

That is the longest forced win in the whole table: two red men against two
black men, and Red wins — in 55 moves of perfect play. Add `--line` to watch
the table play it out.

In code:

```python
from checkers_endgame import Board, Tablebase

tb = Tablebase("endgame4.bin.gz")

# pieces go on the dark squares, where (row + column) is odd
board = Board.from_rows([
    "........",
    "..b.....",
    "........",
    "........",
    "........",
    "..R.....",
    "........",
    "........",
], turn="red")

print(tb.probe(board))       # draw with perfect play
print(tb.best_move(board))   # ((5, 2), (4, 1))  — a move that holds it
```

A king cannot catch a lone man: drawn. Give Red a second king and the same
position becomes a win in four moves. The table knows which, and by how much.

`Board.from_code` also reads the position codec used in
[checkersarena.io](https://checkersarena.io/checkers-solver/) URLs, so any
position you can build on the analysis board can be pasted straight in.

## What is in the box

| File | What it is |
|---|---|
| `endgame4.bin.gz` | The table. One byte per slot, gzipped. |
| `checkers_endgame.py` | Reader, indexer and a complete American-checkers move generator. Standard library only, Python 3.8+. |
| `verify_reader.py` | Checks this reader against reference answers from the generator. |
| `cases.json` | 400 random positions with the answers the generator gave. |
| [`FORMAT.md`](FORMAT.md) | The byte layout and the indexing scheme, in full. |
| [`VERIFICATION.md`](VERIFICATION.md) | How the table was proved correct, four independent ways. |

## Is it right?

That is the only question that matters for a lookup table, because unlike a
search bug, an indexing error never announces itself — it just answers
confidently about a different position. [`VERIFICATION.md`](VERIFICATION.md)
has the detail; the short version is four checks that share no reasoning:

1. **The index is a bijection.** Every position maps to one slot and every
   slot back to one position, checked across every material signature.
2. **Local consistency, exhaustively.** Every one of the 6.4 million entries
   must follow from the entries of its own successors. Run over the whole
   table, not sampled. If every position satisfies the recursion with
   well-founded distances, the assignment *is* the unique solution.
3. **An independent prover agrees.** A separately written search, sharing no
   code with the generator, has to reproduce the exact distance.
4. **Known endings come out right.** King against king is drawn; two kings
   against one wins in 11 moves; three against one in 7. Two thirds of all
   king-versus-king placements really are drawn, and two kings beat one from
   every placement but 34.

And one invariant that needs no reference at all: a game ends when the loser
has nothing left, so **a win always takes an odd number of plies and a loss an
even number**. In the shipped file all 2,675,270 winning distances are odd and
not one is even. Any drift in the unit of distance would break that
immediately.

You can re-run the cross-check yourself:

```bash
python verify_reader.py cases.json
```

```
400 positions checked
  slots     400/400 agree
  verdicts  400/400 agree
  moves     400/400 agree
  parity    160/160 wins odd, 126/126 losses even
```

The reader in this repository was written from the format specification rather
than translated from the generator, so that check is two implementations
agreeing rather than one implementation agreeing with itself.

## Why distances and not just win/loss/draw

Three outcomes would be enough to never throw a win away, and not enough to
ever finish one. Every move in a won position keeps the win, so a table
without distances has no reason to prefer any of them and will shuffle pieces
forever. Storing the distance is what makes the table able to actually deliver
the 55-move win rather than merely know that it exists.

## How it was built

Forwards, not backwards. The obvious way to build a tablebase is retrograde
analysis — generate the *predecessors* of a position, which means writing a
reverse move generator that un-captures pieces and un-crowns kings. That is
new, untested code at the most delicate point in the whole project.

Instead the successor graph is generated with the same rules engine that
validates real games on the live site, and then walked in reverse. No new rule
code, and the move generator is the one that has been exercised by every game
ever played on the site.

Positions are grouped by material signature so memory stays bounded, and the
signatures are solved in an order where each depends only on ones already
finished — with one exception: a signature and its mirror depend on each
other, because only red-to-move positions are stored, so those two are solved
together as a single group.

## Citing it

If this is useful in something you publish, a link is all that is asked — the
licence is CC BY 4.0. There is a `CITATION.cff` in the repository, and GitHub
will format a citation from it for you.

> Checkers Arena (2026). *Checkers endgame tablebase: all positions with four
> pieces or fewer, solved exactly.* https://checkersarena.io/checkers-endgame/

## Limits, stated plainly

- **Four pieces, not more.** Five-piece positions need roughly thirty times the
  space and are not here.
- **American rules only.** No flying kings, captures compulsory, crowning ends
  the turn. The table says nothing about Brazilian, international or Turkish
  draughts, which have different rules and different endings.
- **No positions mid-capture-chain.** A position halfway through a multi-jump
  is not one a turn can start from, so it has no slot.
- **14% of the file is unused.** Piece classes are ranked independently, which
  leaves gaps where two classes would claim the same square. A denser scheme
  exists and is considerably easier to get subtly wrong; the gaps hold a
  constant byte and compress to almost nothing, so the trade was made
  deliberately.

## Licence

The **data** — `endgame4.bin.gz` and `cases.json` — is
[CC BY 4.0](LICENSE): use it anywhere, including commercially, as long as you
credit it. A credit for a dataset is normally a link:

> Checkers endgame tablebase by [Checkers Arena](https://checkersarena.io/),
> licensed under CC BY 4.0.

The **code** — `checkers_endgame.py` and `verify_reader.py` — is MIT, see
[LICENSE-CODE](LICENSE-CODE).
