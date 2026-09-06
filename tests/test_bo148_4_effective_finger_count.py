"""
tests/test_bo148_4_effective_finger_count.py

Regression tests for BO-148.3/.4: playability.
effective_finger_count() -- a barre-aware count of how many
physical fingers a shape genuinely needs -- and its placement
as the FINAL element of chord_service.py's own sort_key tuple,
strictly after position_distance.

Root cause (BO-148 investigation): chord_generator.py's own
_score_candidate() has no finger-count concept at all, only a
flat +10 boolean "is there any barre" bonus with no notion of
HOW MANY fingers a shape needs beyond that. BO-148.2 confirmed
no equivalent metric exists anywhere else in the codebase
(playability.py, chord_service.py, or score_generator.py).

Placement history, not re-litigated here: BO-148.3 first placed
this tie-break immediately after -notes_played (before
-voicing_quality_score/position_distance) -- reverted after a
real, confirmed full-pipeline regression (test_bo36_chord_
corridor's own real F4 case changed fret, because BO-33's own
established position_distance tiebreak never got a chance to
run). BO-148.4 moved it to the LAST position in the tuple
instead -- confirmed via the complete regression suite to
produce zero new failures against the true pre-BO-148.3
baseline. This file exists to give that specific, narrow
placement its own permanent regression coverage, since neither
BO-148.3 nor BO-148.4 added one at the time.

Does not touch, and is not testing, chord_generator.py's own
position-bucket deduplication (BO-148's own original fix) --
that remains a separate, already-covered mechanism.
"""

import sys

sys.path.insert(0, '.')

from playability import effective_finger_count

from fretboard import parse_shape

from chord_service import ChordService

from chord_library import ChordLibrary

from tunings import get_tunings


# ---------------------------------------------------------
# 1 -- effective_finger_count() itself, direct unit coverage
# of every shape from the BO-148.2/.3 design discussion.
# ---------------------------------------------------------

def test_effective_finger_count_matches_proposed_model():

    cases = [
        ("0000", 0),
        ("0002", 1),
        ("0012", 2),
        ("0312", 3),
        ("777(10)", 2),   # one 3-string barre at 7 + one at 10
        ("977(10)", 3),   # 9 alone + a 2-string barre at 7 + 10
        ("0(11)(10)(10)", 2),  # 11 alone + a 2-string barre at 10
        ("0(10)98", 3),   # no barre -- 10, 9, 8 all distinct
    ]

    for shape_text, expected in cases:

        values = parse_shape(shape_text)

        result = effective_finger_count(values)

        assert result == expected, (
            f"{shape_text}: expected {expected} fingers, got "
            f"{result}"
        )


# ---------------------------------------------------------
# 2 -- non-adjacent strings sharing a fret do NOT count as
# one barre finger (a real finger can't skip over a
# different fret in between) -- same adjacency requirement
# _is_simple_barre() already established, reused here.
# ---------------------------------------------------------

def test_non_adjacent_same_fret_costs_two_fingers():

    # strings 0 and 2 both at fret 5, string 1 at a different
    # fret in between -- NOT one barre, two separate fingers.
    values = parse_shape("5354")

    assert effective_finger_count(values) == 4


# ---------------------------------------------------------
# 3 -- the real BO-148 D7/Open G case: finger count is
# consulted, but does NOT decide this specific pair --
# 0(11)(10)(10) still beats 777(10), confirming the earlier
# sort_key components (which tie here) are still what
# actually decides it.
# ---------------------------------------------------------

def test_real_d7_open_g_finger_count_does_not_decide():

    open_g = get_tunings()["Open G"]

    service = ChordService(ChordLibrary())

    shapes = service.get_shapes_for_exact_melody_pitch(
        open_g, "D", 2, "7", "Dominant 7th", melody_pitches={72}
    )

    ranked_shapes = [s.shape for s in shapes]

    assert ranked_shapes.index("0(11)(10)(10)") < (
        ranked_shapes.index("777(10)")
    )


# ---------------------------------------------------------
# 4 -- the real BO-36/BO-33 regression this specific
# placement exists to prevent: position_distance must still
# decide before finger count ever gets a chance to, even
# when the higher-finger-count candidate is the one
# position_distance actually favors.
# ---------------------------------------------------------

def test_position_distance_still_wins_over_finger_count():

    A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]

    service = ChordService(ChordLibrary())

    class _FakeShape:

        def __init__(self, shape, quality_score):

            self.shape = shape

            self.voicing_quality_category = "ROOT_PRESENT"

            self.voicing_quality_score = quality_score

            self.source = "generated"

    # 0356 (3 fingers) is the real, established BO-33 winner
    # over 0(10)88 (only 2 fingers -- fewer than 0356) once a
    # real preferred_melody_fret makes position_distance
    # discriminate -- confirmed directly, BO-148.3's own
    # investigation traced this exact pair.
    fewer_fingers_shape = _FakeShape("0(10)88", 21.5)

    more_fingers_shape = _FakeShape("0356", 21.5)

    assert effective_finger_count(
        parse_shape(fewer_fingers_shape.shape)
    ) < effective_finger_count(
        parse_shape(more_fingers_shape.shape)
    )

    service.get_shapes = lambda *a, **k: [
        fewer_fingers_shape, more_fingers_shape
    ]

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "7", "Dominant 7th", {70},
        preferred_melody_fret=6
    )

    assert ranked[0].shape == "0356", (
        "position_distance must still decide this real, "
        "established BO-33 case before finger count is ever "
        "consulted, even though the winner has MORE fingers "
        "than the shape it beats"
    )


# ---------------------------------------------------------
# 5 -- a genuine positive case: when every earlier sort_key
# component ties, finger count DOES decide -- confirming the
# mechanism actually activates somewhere, not just that it
# stays out of the way.
# ---------------------------------------------------------

def test_finger_count_decides_when_everything_else_ties():

    A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]

    service = ChordService(ChordLibrary())

    class _FakeShape:

        def __init__(self, shape, quality_score):

            self.shape = shape

            self.voicing_quality_category = "ROOT_PRESENT"

            self.voicing_quality_score = quality_score

            self.source = "generated"

    # Same quality, and BOTH shapes contain the same melody
    # pitch (72 -- confirmed directly, sounding_notes()) so
    # contains_melody_pitch ties at True for both, not the
    # empty-set early-return path get_shapes_for_exact_melody_
    # pitch() itself takes when no melody_pitches are supplied
    # at all. No preferred_melody_fret (position_distance ties
    # at 0 for both) -- isolates finger count as the only thing
    # left that can decide.
    three_fingers = _FakeShape("0(10)98", 21.5)

    two_fingers = _FakeShape("0(11)(10)(10)", 21.5)

    service.get_shapes = lambda *a, **k: [
        three_fingers, two_fingers
    ]

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "7", "Dominant 7th", {72}
    )

    assert ranked[0].shape == "0(11)(10)(10)", (
        "with every earlier sort_key component genuinely tied, "
        "the fewer-finger shape should win"
    )
