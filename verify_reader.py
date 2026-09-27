"""
Check this Python reader against reference answers produced by the JavaScript
implementation the tablebase was generated with.

Two independent implementations of one indexing scheme agreeing on hundreds of
random positions is the check that matters: a single off-by-one in the ranking
would make every lookup describe a different position, confidently and
silently. Slot numbers are compared too, not only verdicts, because two wrong
slots can still hold the same byte.

    python verify_reader.py cases.json

`cases.json` is a list of {code, slot, outcome, plies, moves, legal}. The
repository ships one; regenerate it from the site's own engine if you want to
check against a fresh build.
"""

import json
import sys

from checkers_endgame import (
    Board,
    Tablebase,
    slot_of,
    RED,
    square_name,
)


def main(argv):
    cases_path = argv[0] if argv else "cases.json"
    table_path = argv[1] if len(argv) > 1 else "endgame4.bin.gz"

    with open(cases_path, encoding="utf-8") as fh:
        cases = json.load(fh)
    tb = Tablebase(table_path)

    bad_slot = bad_verdict = bad_moves = 0
    for case in cases:
        board = Board.from_code(case["code"])

        # 1) the index: same slot number as the generator computed
        query = board if board.turn == RED else board.rotated()
        if slot_of(query) != case["slot"]:
            bad_slot += 1
            if bad_slot <= 3:
                print(f"slot mismatch on {case['code']}: "
                      f"python {slot_of(query)} vs js {case['slot']}")

        # 2) the verdict and the exact distance
        result = tb.probe(board)
        if (result is None
                or result.outcome != case["outcome"]
                or result.plies != case["plies"]
                or result.moves != case["moves"]):
            bad_verdict += 1
            if bad_verdict <= 3:
                print(f"verdict mismatch on {case['code']}: "
                      f"python {result} vs js {case['outcome']}/{case['plies']}")

        # 3) the rules: the move generator has to agree too, or "play it out"
        #    would wander off into positions the table never promised anything
        #    about
        mine = sorted(f"{m[0][0]}{m[0][1]}{m[1][0]}{m[1][1]}"
                      for m in board.legal_moves())
        if mine != sorted(case["legal"]):
            bad_moves += 1
            if bad_moves <= 3:
                print(f"legal moves differ on {case['code']}: "
                      f"python {mine} vs js {sorted(case['legal'])}")

    total = len(cases)
    print(f"\n{total} positions checked")
    print(f"  slots     {total - bad_slot}/{total} agree")
    print(f"  verdicts  {total - bad_verdict}/{total} agree")
    print(f"  moves     {total - bad_moves}/{total} agree")

    # 4) an invariant that needs no reference at all: a game ends when the
    #    loser has nothing left, so a win always takes an odd number of plies
    #    and a loss an even one. Any drift in the unit shows up here.
    odd_wins = sum(1 for c in cases if c["outcome"] == "win" and c["plies"] % 2 == 1)
    wins = sum(1 for c in cases if c["outcome"] == "win")
    even_losses = sum(1 for c in cases if c["outcome"] == "loss" and c["plies"] % 2 == 0)
    losses = sum(1 for c in cases if c["outcome"] == "loss")
    print(f"  parity    {odd_wins}/{wins} wins odd, {even_losses}/{losses} losses even")

    failed = bad_slot or bad_verdict or bad_moves or odd_wins != wins or even_losses != losses
    print("\nFAILED" if failed else "\nOK — the two implementations agree")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
