# File format

`endgame4.bin.gz` is a gzip stream. Unpacked it is **7,455,300 bytes**, one
byte per slot, with no header — the length *is* the check: any other length
means a truncated or foreign file, and a reader should refuse it rather than
answer from it.

Of those slots, **6,408,836** hold a real position. The remaining 1,046,464
(14.0%) are gaps left by the indexing scheme and hold `0`.

## The byte

| Value | Meaning |
|---|---|
| `0` | Unused slot — no legal position maps here |
| `1` | Draw with perfect play |
| `2 … 127` | **Red (the side to move) wins** in `value − 2` plies |
| `128 … 255` | **Red loses** in `value − 128` plies |

A *ply* is a single move by one side. The longest win in the file is 109
plies; the encoding allows up to 125.

Converting plies to whole moves is exact rather than rounded. A game ends when
the loser has no pieces or no move, so **a win always takes an odd number of
plies and a loss an even number**:

```python
moves = (plies + 1) // 2 if plies % 2 else plies // 2
```

## Only red to move

The file stores **red-to-move positions only**. Rotating the board 180° and
swapping the colours maps the game exactly onto itself: a rotated red piece
moves toward row 7 the way a black piece does, and the two crowning rows map
onto each other. So a black-to-move query is transformed first, and the file
is half the size it would otherwise be.

```python
board = board if board.turn == "red" else board.rotated()
```

## Board coordinates

Rows run 0–7 from the top; columns 0–7 from the left. **Row 0 is Black's back
row, row 7 is Red's back row, and Red moves toward row 0.**

Play happens on the 32 dark squares, where `(row + column)` is odd. They are
numbered 0–31 in row-major order:

```
row 0:  .  0  .  1  .  2  .  3
row 1:  4  .  5  .  6  .  7  .
row 2:  .  8  .  9  . 10  . 11
   …
row 7: 28  . 29  . 30  . 31  .
```

The site's own display uses files `a`–`h` and ranks `1`–`8` with rank 1 at the
bottom, so square 0 above is `b8` and square 28 is `a1`.

## The index

### Piece domains

A red man can never stand on row 0, nor a black man on row 7 — arriving there
crowns it. Those positions do not exist, so men are indexed over **28**
squares and kings over all **32**:

| Class | Domain | Size |
|---|---|---|
| Red man | dark squares with row ≠ 0 | 28 |
| Red king | all dark squares | 32 |
| Black man | dark squares with row ≠ 7 | 28 |
| Black king | all dark squares | 32 |

A domain is an ordered list, and a piece's *domain position* is its index
within that list — not the square number. This matters: the rankings below are
over domain positions.

### Material signatures

A signature is `(red men, red kings, black men, black kings)`. Both sides must
have at least one piece; a side with none has already lost and needs no entry.
Signatures are enumerated in this exact nesting order, and the blocks appear
in the file in that order:

```python
for rm in range(5):
    for rk in range(5 - rm):
        for bm in range(5 - rm - rk):
            for bk in range(5 - rm - rk - bm):
                if rm + rk == 0 or bm + bk == 0:
                    continue
                yield (rm, rk, bm, bk)
```

Each block is as large as the number of arrangements it can hold:

```
size(rm, rk, bm, bk) = C(28, rm) · C(32, rk) · C(28, bm) · C(32, bk)
```

and a block's offset is the sum of the sizes of all blocks before it. Both the
generator and every reader derive the offsets this way; there is no stored
table of them to disagree with.

### Ranking a set of pieces

Pieces of one class are indistinguishable, so a class is a **set** of domain
positions, ranked with the combinatorial number system. For a sorted subset
`a₀ < a₁ < …`:

```
rank = Σ C(aᵢ, i + 1)
```

This is a bijection onto `0 … C(n, k) − 1`: every arrangement gets exactly one
rank and every rank one arrangement.

### Putting it together

Within a block, the four class ranks are combined in mixed radix — red men
most significant, black kings least:

```
index = ((rank(rm) · C(32, |rk|) + rank(rk)) · C(28, |bm|)
         + rank(bm)) · C(32, |bk|) + rank(bk)

slot  = offset(signature) + index
```

### The gaps

Each class is ranked independently, so an arrangement that puts two pieces on
the same square gets a slot even though the position is impossible. Those
slots hold `0` and are never read. They are 14.0% of the file, they compress
to almost nothing, and the alternative — a joint ranking over shared squares —
is denser and considerably easier to get subtly wrong.

## Positions with no slot

A reader must return "not in the table", not a guess, for any of these:

- more than four pieces, or a side with none left
- a man standing on its own crowning row
- a piece on a light square
- a position in the middle of a capture chain — not something a turn can start
  from, so it has no slot

## A complete reader

`checkers_endgame.py` in this repository implements all of the above in about
two hundred lines of standard-library Python, and `verify_reader.py` checks it
against reference answers from the generator: 400 positions, agreeing on slot
numbers, verdicts, distances and legal moves.
