"""
tests/test_bo74_preceding_fd_hp_gate.py

Regression tests for BO-74: preceding_fd_violation (BO-37) remains
authoritative only while the immediately preceding CHOSEN melody
position is still within the hand position the preceding chord
established. Reuses chord_hp_span() (BO-59/60) unmodified -- this
is a gate on RELEVANCE only, not a redesign of the exact (string,
fret) matching itself.

Real motivating case (BO-71/72/73 investigation): The Christmas
Song / A Modal Sawmill and Double D -- an Am chord establishes HP
(7,10); the real G4 immediately following it is chosen at fret 5,
outside that HP; the following A4 was previously still incorrectly
pulled toward the Am shape's own exact fret-7 position regardless.
"""

import sys

sys.path.insert(0, '.')

from score_generator import _choose_melody_position

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


DOUBLE_D = get_tunings()["Double D"]

# The real Am shape's own two fretted positions (string_index 1
# and 2, absolute frets 10 and 7 -- confirmed directly against
# the real generated FD data during the BO-72/73 investigation).
# Ordering matches parse_shape()'s own one-value-per-string
# format: [string0, string1, string2, string3].
REAL_AM_SHAPE = [None, 10, 7, None]


# ---------------------------------------------------------
# Test A -- intervening melody leaves the preceding chord's HP:
# preceding_fd_violation must no longer favor the old shape
# ---------------------------------------------------------

def test_intervening_melody_outside_hp_neutralizes_preceding_fd():

    open_notes = DOUBLE_D.notes[1:] + [DOUBLE_D.notes[0]]

    # G4 at string 2/fret 5 -- real, confirmed outside the Am
    # shape's own established HP (7,10).
    result = _choose_melody_position(
        69, open_notes,  # A4
        preceding_chord_shape_values=REAL_AM_SHAPE,
        previous_position={"string": 2, "fret": 5, "score": 9}
    )

    # With preceding_fd_violation neutralized, string 2/fret 7 (an
    # exact Am-shape match) must NOT automatically win the way it
    # did before BO-74 -- confirmed directly: without the gate,
    # this call returns fret 7. The remaining, unmodified scoring
    # mechanisms decide the actual result instead (BO-74 does not
    # dictate what that result is -- only that the old shape can
    # no longer force it).
    assert not (
        result["string"] == 2 and result["fret"] == 7
    ), (
        "preceding_fd_violation still favored the old Am shape's "
        "exact position despite the intervening note leaving its "
        "HP"
    )


# ---------------------------------------------------------
# Test B -- intervening melody stays inside the HP (but is NOT
# an exact chord-shape position): existing behavior preserved
# ---------------------------------------------------------

def test_intervening_melody_inside_hp_preserves_preceding_fd():

    open_notes = DOUBLE_D.notes[1:] + [DOUBLE_D.notes[0]]

    # fret 8 is inside the Am shape's own HP (7,10) but is NOT
    # one of the shape's own two real fretted positions (7, 10)
    # -- this is the deliberate test of the conceptual distinction
    # BO-74 must preserve: HP membership gates relevance; it does
    # NOT replace the underlying exact-match preference itself.
    result = _choose_melody_position(
        69, open_notes,
        preceding_chord_shape_values=REAL_AM_SHAPE,
        previous_position={"string": 1, "fret": 8, "score": 5}
    )

    assert result["string"] == 2

    assert result["fret"] == 7


# ---------------------------------------------------------
# Test C -- no intervening melody note at all: existing BO-37
# behavior preserved exactly (previous_position is None)
# ---------------------------------------------------------

def test_no_intervening_melody_preserves_existing_bo37_behavior():

    open_notes = DOUBLE_D.notes[1:] + [DOUBLE_D.notes[0]]

    # No previous_position passed at all -- matches every
    # existing BO-37 test's own real scenario (chord immediately
    # precedes the melody note, no evidence the hand moved).
    result = _choose_melody_position(
        69, open_notes,
        preceding_chord_shape_values=REAL_AM_SHAPE,
    )

    assert result["string"] == 2

    assert result["fret"] == 7


# ---------------------------------------------------------
# Test D -- an open-string intervening note must not be treated
# as having left the HP (it tells us nothing about hand position)
# ---------------------------------------------------------

def test_open_string_intervening_note_preserves_preceding_fd():

    open_notes = DOUBLE_D.notes[1:] + [DOUBLE_D.notes[0]]

    # An open-string previous_position (fret 0) is real evidence
    # of nothing -- per BO-59's own established principle, an
    # open string never establishes or moves HP, so it must be
    # treated the same as previous_position being None entirely,
    # not as "definitely left the HP".
    result = _choose_melody_position(
        69, open_notes,
        preceding_chord_shape_values=REAL_AM_SHAPE,
        previous_position={"string": 3, "fret": 0, "score": 6}
    )

    assert result["string"] == 2

    assert result["fret"] == 7


# ---------------------------------------------------------
# Test E -- real Christmas Song / A Modal Sawmill case (the
# original BO-71/72/73 motivating example)
# ---------------------------------------------------------

def test_real_christmas_song_a4_g4_am_case():

    import os

    p = MuseScoreFile(
        "The_Christmas_Song_-_Double_D__aDADE__measures_14-16"
        ".mscz"
    )

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, DOUBLE_D, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo74_real_case.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g4_entry = next(
            e for e in trace
            if e.measure == 15 and e.beat == 0.0
        )

        a4_entry = next(
            e for e in trace
            if e.measure == 15 and e.beat == 0.5
        )

        # G4 unaffected by BO-74 -- confirmed real, outside the
        # Am HP either way.
        assert g4_entry.fret == 5

        # A4 must no longer be forced to the old Am shape's own
        # exact fret-7 position -- confirmed directly: this was
        # (2, 7) before BO-74.
        assert not (
            a4_entry.string == 2 and a4_entry.fret == 7
        ), (
            "A4 is still being pulled toward the old Am shape's "
            "exact position despite G4 leaving its HP"
        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
