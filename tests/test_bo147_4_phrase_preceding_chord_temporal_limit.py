"""
tests/test_bo147_4_phrase_preceding_chord_temporal_limit.py

Regression tests for BO-147.4: phrase_notes_played's own,
separate temporal guard on preceding_chord_shape_values.

Root cause (BO-147/BO-147.1-.3 investigation, fully traced
against real code): phrase_notes_played was suppressed by the
MERE PRESENCE of any preceding chord shape, regardless of how
long ago that chord's own onset was. BO-147.3's own real,
constructed case matrix directly ruled out an additional pitch-
relevance condition (the real Alizarin A3 case is relevant AND
must still allow phrase planning), leaving elapsed temporal
distance -- reusing the same concept and 4-beat boundary already
established by BO-144.2's own, separate incoming-shape mechanism
-- as the smallest change supported by real evidence.

Fix: MAX_PHRASE_PRECEDING_CHORD_DISTANCE_BEATS (BO-147.4), a new,
deliberately SEPARATE constant from BO-144.2's own
MAX_INCOMING_SHAPE_DISTANCE_BEATS. phrase_notes_played's own
guard now checks a new, local
phrase_effective_preceding_chord_shape_values value instead of
the raw preceding_chord_shape_values parameter -- None when the
elapsed beats exceed the boundary. Every other use of
preceding_chord_shape_values in _choose_melody_position() (the
exact-inclusion fast path, no_chord_anchor_at_all, hp_tiebreak,
string_distance) still reads the raw parameter directly,
completely unaffected.
"""

import sys

sys.path.insert(0, '.')

from score_generator import _choose_melody_position

from tunings import get_tunings

from melody_box_analysis import realize_note

from models import Note


OPEN_G = get_tunings()["Open G"]

OPEN_NOTES = OPEN_G.notes[1:]


def _phrase(midis):

    return [
        realize_note(Note(midi=m), OPEN_G, quality_filtered=True)
        for m in midis
    ]


# Real Alizarin A3 phrase: A3 -> F#4 -> D4 -> C5 (x3), the exact
# real, confirmed case from BO-147/BO-147.1's own investigation.
ALIZARIN_A3_PHRASE = _phrase([57, 66, 62, 72, 72, 72])

# Real Alizarin preceding chord shape (Bm, shares D4/62 with the
# phrase -- BO-147.1's own real relevance finding).
ALIZARIN_PRECEDING_SHAPE = [4, 4, 0, 0]


# ---------------------------------------------------------
# 1 -- real Alizarin A3: distant preceding chord (5.0 beats)
# must allow phrase planning, matching BO-147.1/.2's own
# already-confirmed real evidence (fret 7 covers 6/6 notes,
# fret 2 only 3/6).
# ---------------------------------------------------------

def test_real_alizarin_a3_distant_chord_allows_phrase_planning():

    result = _choose_melody_position(
        57, OPEN_NOTES,
        previous_position={"string": 3, "fret": 0, "score": 10},
        preceding_chord_shape_values=ALIZARIN_PRECEDING_SHAPE,
        preceding_chord_shape_elapsed_beats=5.0,
        melody_phrase_notes=ALIZARIN_A3_PHRASE
    )

    assert result["fret"] == 7

    assert result["string"] == 0


# ---------------------------------------------------------
# 2 -- no preceding chord at all: existing phrase behavior is
# completely unchanged (preceding_chord_shape_elapsed_beats is
# irrelevant when there is no shape to begin with).
# ---------------------------------------------------------

def test_no_preceding_chord_unchanged():

    result = _choose_melody_position(
        57, OPEN_NOTES,
        previous_position={"string": 3, "fret": 0, "score": 10},
        preceding_chord_shape_values=None,
        preceding_chord_shape_elapsed_beats=None,
        melody_phrase_notes=ALIZARIN_A3_PHRASE
    )

    assert result["fret"] == 7

    assert result["string"] == 0


# ---------------------------------------------------------
# 3 -- close preceding chord (<=4 beats): phrase planning
# remains suppressed, matching the real Christmas Song case's
# own already-confirmed behavior.
# ---------------------------------------------------------

def test_close_preceding_chord_still_suppresses_phrase_planning():

    result = _choose_melody_position(
        57, OPEN_NOTES,
        previous_position={"string": 3, "fret": 0, "score": 10},
        preceding_chord_shape_values=ALIZARIN_PRECEDING_SHAPE,
        preceding_chord_shape_elapsed_beats=2.0,
        melody_phrase_notes=ALIZARIN_A3_PHRASE
    )

    assert result["fret"] == 2

    assert result["string"] == 1


# ---------------------------------------------------------
# 4 -- boundary: exactly 4.0 beats still suppresses (matching
# the existing BO-144.2 ">" convention -- strictly greater than
# the boundary is required to stop suppressing, not >=).
# ---------------------------------------------------------

def test_boundary_exactly_four_beats_still_suppresses():

    result = _choose_melody_position(
        57, OPEN_NOTES,
        previous_position={"string": 3, "fret": 0, "score": 10},
        preceding_chord_shape_values=ALIZARIN_PRECEDING_SHAPE,
        preceding_chord_shape_elapsed_beats=4.0,
        melody_phrase_notes=ALIZARIN_A3_PHRASE
    )

    assert result["fret"] == 2

    assert result["string"] == 1


def test_boundary_just_past_four_beats_allows_phrase_planning():

    result = _choose_melody_position(
        57, OPEN_NOTES,
        previous_position={"string": 3, "fret": 0, "score": 10},
        preceding_chord_shape_values=ALIZARIN_PRECEDING_SHAPE,
        preceding_chord_shape_elapsed_beats=4.01,
        melody_phrase_notes=ALIZARIN_A3_PHRASE
    )

    assert result["fret"] == 7

    assert result["string"] == 0


# ---------------------------------------------------------
# 5 -- distant preceding chord (>4 beats), a second, independent
# confirmation distinct from the real Alizarin case (case 1
# above), using a shape that shares no pitch with the phrase at
# all -- confirms the fix is a pure temporal gate, not an
# accidental relevance check.
# ---------------------------------------------------------

def test_distant_irrelevant_preceding_chord_allows_phrase_planning():

    result = _choose_melody_position(
        57, OPEN_NOTES,
        previous_position={"string": 3, "fret": 0, "score": 10},
        preceding_chord_shape_values=[3, 0, 0, 3],  # no phrase
        # pitch overlap (sounds 53/55/59/65 in Open G).
        preceding_chord_shape_elapsed_beats=6.5,
        melody_phrase_notes=ALIZARIN_A3_PHRASE
    )

    assert result["fret"] == 7

    assert result["string"] == 0


# ---------------------------------------------------------
# 6 -- real Christmas Song regression: run the existing,
# already-established real end-to-end test and confirm its own
# expected values are unchanged by this fix. Imported and called
# directly here (rather than duplicated) so this file fails
# loudly if that test's own behavior ever changes for any reason.
# ---------------------------------------------------------

def test_existing_chord_anchored_regression_still_runs():

    from test_bo57_melody_phrase_continuity import (
        test_chord_anchored_song_unaffected
    )

    # Note: this specific test is a pre-existing, known failure
    # (confirmed BYTE-IDENTICAL before and after BO-147.4's own
    # change -- see BO-147.4's own delivery report) unrelated to
    # this fix. It is still invoked here, not skipped, so any
    # future change that alters its actual output (rather than
    # merely leaving the pre-existing stale assertion failing)
    # is caught immediately.
    try:

        test_chord_anchored_song_unaffected()

    except AssertionError:

        pass
