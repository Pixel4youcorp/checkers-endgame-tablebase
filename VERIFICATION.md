# How this table was proved correct

A lookup table fails differently from a search engine. A search bug shows up
as a bad move you can argue with; an **indexing** bug makes the table answer
confidently about a different position, and no amount of extra thinking ever
exposes it. So the table is checked from four directions that share no
reasoning, plus one invariant that needs no reference at all.

All of this lives in `tests/test-endgame.js` in the Checkers Arena repository
(23 assertions). The exhaustive pass in check 2 is run before shipping, not in
the normal suite, because it takes about four minutes.

---

## 1 · The index is a bijection

If two positions can share a slot, everything downstream is meaningless. So
the numbering is checked as a mathematical object, before any game logic:

- **rank / unrank round-trip** over every subset size the table uses: ranking
  an arrangement and unranking the result returns the same arrangement.
- **slot → board → slot** for slots drawn from every material signature.
- **The rotation symmetry is really a symmetry.** Rotating the board 180° and
  swapping the colours must give a position that is not merely *encodable*
  but *the same game* — checked by confirming it has the same number of legal
  moves.

That last one matters more than it looks. The whole file is half-size because
of that symmetry. If the transform were subtly wrong, every black-to-move
answer would be wrong, and nothing else in the pipeline would notice.

## 2 · Local consistency, over every entry

Every value must follow from the values of its own successors:

- A position is **won in _n_ plies** if some move leads to a position the
  opponent loses in _n_−1.
- A position is **lost in _n_ plies** if every move leads to a position the
  opponent wins, and the longest of those is _n_−1.
- A position is **drawn** if no move wins and some move avoids losing.

Run over **all 6,408,836 entries**, not sampled. This is stronger than it
sounds: if every position satisfies the recursion and the distances are
well-founded, the assignment *is* the unique solution to the game. There is no
room left for a consistent-but-wrong table.

## 3 · An independent prover has to agree

`forcedWin()` from `tools/make-puzzles.js` is a plain depth-limited search
written for a different purpose and sharing no code with the tablebase
generator. On sampled positions it must agree with the table on the **exact
distance**, not merely on who wins.

This is the check that would catch a mistake in the *building* rather than in
the *indexing* — a wrong sweep order, a signature solved before its
dependencies.

## 4 · Endings whose answers are already known

- King against king: **drawn**.
- Two kings against one: **won in 11 moves**.
- Three kings against one: **won in 7 moves**.
- Across all placements: two thirds of king-versus-king positions are drawn,
  and two kings beat one from every placement but 34.

These come from the literature, not from our own code, so they are the only
check here that could catch a shared misunderstanding of the rules.

---

## The behavioural test: it has to actually finish

The sharpest check is not a comparison at all. **The table plays itself,** and
the win has to arrive in exactly the promised number of plies — 21 promised,
21 played.

This is what distances are for. With only win/loss/draw, a table can avoid
throwing a win away, but since *every* move in a won position keeps the win it
would have no reason to prefer any of them, and would shuffle pieces forever
while remaining technically correct.

## The invariant that needs nothing

A game ends when the loser has no pieces or no legal move, and the winner
plays the first and last ply of the sequence. So:

> **Every win takes an odd number of plies. Every loss takes an even number.**

In the shipped file all **2,675,270** winning distances are odd and not one is
even. Any drift between "plies" and "moves" anywhere in the pipeline breaks
this immediately, which is why it is checked on the finished artefact rather
than on intermediate state.

## Two independent readers agree

The Python reader in this repository was written from
[`FORMAT.md`](FORMAT.md), not translated from the generator. `verify_reader.py`
compares it against reference answers from the JavaScript implementation the
table was built with:

```
400 positions checked
  slots     400/400 agree
  verdicts  400/400 agree
  moves     400/400 agree
  parity    160/160 wins odd, 126/126 losses even
```

Slot **numbers** are compared, not only verdicts — two wrong slots can happen
to hold the same byte, and a check that only compared outcomes would let that
through.

---

## A mistake worth recording

The first version of the behavioural test placed a black man on row 7 to pin
it in place. That position cannot occur: a man arriving on its own crowning
row is crowned. The table correctly refused to answer, and **the test read the
refusal as a failure**.

The table was right and the test was wrong, which is the failure mode to watch
for when checking something exhaustive: it is easy to write a check that
demands an answer to a question with no answer.
