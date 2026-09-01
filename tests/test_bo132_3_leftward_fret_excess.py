"""
tests/test_bo132_3_leftward_fret_excess.py

Focused tests for BO-132.3: the leftward-fret-excess rule in
playability.py. IMPORTANT NOTE ON NUMBERING (the exact confusion
BO-132.1 fell into, corrected in BO-132.2): the player's own
real-world string numbering is the REVERSE of BO's internal
shape-string position order. "Rejected because an earlier/
leftward position exceeds a later/rightward position by more
than 2" is stated here in terms of BO's own raw shape-string
position order (index 0 = leftmost character), matching what the
implementation itself actually checks -- not the player's own
string-number labels, which run in the opposite direction.
"""

import sys

sys.path.insert(0, '.')

from playability import evaluate


# ---------------------------------------------------------
# Required real/named examples
# ---------------------------------------------------------

def test_7470_rejected():

    result = evaluate('7470')

    assert result.accepted is False, (
        "'7470' (position0=7, position1=4, excess 3) should be "
        "rejected by the leftward-fret-excess rule."
    )


def test_5502_rejected():

    result = evaluate('5502')

    assert result.accepted is False, (
        "'5502' (position0/1=5, position3=2, excess 3) should be "
        "rejected by the leftward-fret-excess rule."
    )


def test_5520_rejected():

    result = evaluate('5520')

    assert result.accepted is False, (
        "'5520' (position0/1=5, position2=2, excess 3) should be "
        "rejected by the leftward-fret-excess rule."
    )


def test_2552_rejected():

    # BO-132.3's own explicit decision: 2552 is technically
    # fingerable via a barre (confirmed directly by the player
    # earlier this project), but is deliberately blocked anyway
    # as a poor practical choice -- no exception was created.
    result = evaluate('2552')

    assert result.accepted is False, (
        "'2552' should be rejected -- BO-132.3 deliberately does "
        "not create an exception for it, despite being "
        "technically fingerable via a barre."
    )


# ---------------------------------------------------------
# Boundary and direction tests
# ---------------------------------------------------------

def test_exactly_two_fret_difference_accepted():

    # '5550': position0/1/2 all fret 5, difference 0 -- well
    # within the allowed range. Confirms a real 2-or-fewer
    # difference passes; using the player's own stated preferred
    # alternative to 5520 directly.
    result = evaluate('5550')

    assert result.accepted is True, (
        f"'5550' should be accepted (no fretted-pair difference "
        f"exceeds 2), got accepted=False: {result.reason!r}"
    )


def test_rightward_higher_than_leftward_accepted():

    # '(11)0(11)0': position0=11, position2=11 -- equal, and the
    # only fretted pair. The player's own preferred alternative
    # for the Double C/G case when melody genuinely requires a
    # high position (BO-132.1's own example). Confirms a shape
    # where no earlier position exceeds a later one by more than
    # 2 is accepted by this rule specifically (other rules, e.g.
    # span, are not exercised by this particular shape and are
    # not this test's concern).
    result = evaluate('(11)0(11)0')

    assert result.accepted is True, (
        f"'(11)0(11)0' should be accepted by the leftward-fret-"
        f"excess rule, got accepted=False: {result.reason!r}"
    )


def test_open_strings_do_not_participate():

    # '5002': position0=5, position3=2 -- the only two fretted
    # positions (position1/2 are open, per this shape's own
    # string). Difference is 5-2=3, still a real violation
    # between the two genuinely fretted positions -- confirms
    # open strings are correctly skipped (not treated as fret 0
    # in the comparison), while a real excess between the
    # remaining fretted pair is still caught.
    result = evaluate('5002')

    assert result.accepted is False, (
        "'5002' should be rejected: position0 (fret 5) exceeds "
        "position3 (fret 2) by 3, with the open strings between "
        "them correctly not participating in the comparison at "
        "all."
    )

    # A shape where the only fretted pair has an allowed (<=2)
    # difference, with opens between them, should pass -- proves
    # opens aren't accidentally contributing to a violation.
    result_ok = evaluate('4003')

    assert result_ok.accepted is True, (
        f"'4003' (fretted positions differ by exactly 1, opens "
        f"between them) should be accepted, got accepted=False: "
        f"{result_ok.reason!r}"
    )
