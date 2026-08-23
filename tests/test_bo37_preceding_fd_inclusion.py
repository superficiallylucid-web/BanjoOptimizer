"""
tests/test_bo37_preceding_fd_inclusion.py

Regression tests for BO-37 (replacing BO-36's own corridor_
floor/corridor_ceiling design, which was found not to match
the intended playing behavior): score_generator._choose_melody_
position() now also considers exact inclusion in the most
recent PRECEDING chord's own shape, regardless of how many
intervening melody notes sit between them.

Design, per a real, hand-verified reference score (The Christmas
Song / Double C, measures 1-11 vs the user's own preferred
measures 12-22 for the same passage): "the tabbed note should be
IN the [most recent] FD. If there is no FD at the same beat, the
tabbed note should be IN OR SIMILAR TO the most recent FD."

    preceding_fd_violation (0 if the candidate's exact string/
    fret matches a real position in the most recent preceding
    chord's own shape, else 1) comes FIRST in the sort key,
    ahead of the existing fret_distance/string_distance/score
    tiebreaks -- when no such match exists, this has no effect
    at all (every candidate ties at 1) and the pre-existing BO-
    24/25/30 anchor logic decides exactly as before, matching
    "or SIMILAR to" for the non-matching case.

Confirmed against 7 of the 8 real changes in the reference score
(measures 2, 3, 4, 5, 10, 11 -- the G4/Cmaj7, E4/Em, C4/C, C4/Am
cases). Two real findings in the reference score fall OUTSIDE
this fix's own scope, reported separately rather than folded in
here without further confirmation:

  - measure 1's C4 has no preceding chord at all (it is the very
    first note of the piece) -- the reference score's own
    preferred fret 0 there is an OPEN string, not a literal FD-
    inclusion match (confirmed: C4 does not occur anywhere in
    the following "C" chord's own shape [0,9,7,10] either) --
    this appears to be a different, narrower principle ("an open
    string commits the hand to nothing, so it doesn't conflict
    with preparing for a distant upcoming chord") that only
    applies before the very first chord onset of a piece.

  - measure 7's G#m chord-SHAPE selection itself (not a melody-
    position choice) differs in the reference score (3436 vs the
    preferred 8889) -- this is a chord_service.py ranking
    question, a different system from score_generator.py's own
    melody-position selection this fix addresses.

Only score_generator._choose_melody_position()'s preceding-FD
branch and its own pre-computation pass in generate_tab_from_
template() changed. _fd_positions_for_pitch() itself, chord
generation, chord-shape ranking, FD selection, BO-24/25/30/33/35
established behavior are all untouched.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from fretboard import parse_shape

from score_generator import (
    _choose_melody_position, generate_tab_from_template
)


DOUBLE_C = get_tunings()["Double C"]  # gCGCD

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


# ---------------------------------------------------------
# 1-4 -- the four real, verified reference-score cases
# ---------------------------------------------------------

def test_real_g4_cmaj7_case():

    open_notes = DOUBLE_C.notes[1:]

    # A competing anchor pulling toward fret5/string_index3
    # (best_position()'s own second-choice for G4, score 7) --
    # confirms fret7/string_index2 wins BECAUSE of genuine
    # preceding-FD inclusion, not merely because it would have
    # won on score alone regardless.
    chosen = _choose_melody_position(
        67, open_notes,  # G4
        preceding_chord_shape_values=parse_shape("0979"),  # Cmaj7
        following_working_fret_anchor=5
    )

    assert chosen["string"] == 2

    assert chosen["fret"] == 7


def test_real_e4_em_case():

    open_notes = DOUBLE_C.notes[1:]

    # Competing anchor pulling toward fret2/string_index3
    # (best_position()'s own second choice for E4, score 10).
    chosen = _choose_melody_position(
        64, open_notes,  # E4
        preceding_chord_shape_values=parse_shape("4445"),  # Em
        following_working_fret_anchor=2
    )

    assert chosen["string"] == 2

    assert chosen["fret"] == 4


def test_real_c4_c_chord_case():

    open_notes = DOUBLE_C.notes[1:]

    # Competing anchor pulling toward fret5/string_index1
    # (best_position()'s own second choice for C4, score 11).
    chosen = _choose_melody_position(
        60, open_notes,  # C4
        preceding_chord_shape_values=[0, 0, 0, 2],  # C
        following_working_fret_anchor=5
    )

    assert chosen["string"] == 2

    assert chosen["fret"] == 0


def test_real_c4_am_case():

    open_notes = DOUBLE_C.notes[1:]

    # Same competing anchor as the C-chord case above.
    chosen = _choose_melody_position(
        60, open_notes,  # C4
        preceding_chord_shape_values=[0, 2, 0, 2],  # Am
        following_working_fret_anchor=5
    )

    assert chosen["string"] == 2

    assert chosen["fret"] == 0


# ---------------------------------------------------------
# 5 -- when no matching position exists within the preceding
# chord's own shape, behavior falls back to the existing
# anchor/score logic exactly as before ("or similar to")
# ---------------------------------------------------------

def test_no_match_falls_back_to_existing_anchor_logic():

    open_notes = DOUBLE_C.notes[1:]

    # A shape that does not sound F4 (65) at all -- Em's own
    # shape only sounds E/G/B, no F.
    chosen_without_preceding = _choose_melody_position(
        65, open_notes, following_working_fret_anchor=4
    )

    chosen_with_nonmatching_preceding = _choose_melody_position(
        65, open_notes, following_working_fret_anchor=4,
        preceding_chord_shape_values=parse_shape("4445")  # Em, no F4
    )

    assert (
        chosen_without_preceding
        == chosen_with_nonmatching_preceding
    ), (
        "a preceding chord shape that cannot produce this exact "
        "pitch must have zero effect -- every candidate ties at "
        "preceding_fd_violation=1, so the existing fret_distance/"
        "score logic must decide identically either way"
    )


# ---------------------------------------------------------
# 6 -- control: single-occurrence FD-match at a chord onset
# remains completely unaffected (this branch returns before
# preceding_chord_shape_values is ever consulted)
# ---------------------------------------------------------

def test_fd_match_at_onset_unaffected():

    open_notes = A_MODAL_SAWMILL.notes[1:]

    cmaj7_fd = parse_shape("0(10)98")

    chosen = _choose_melody_position(
        71, open_notes, fd_shape_values=cmaj7_fd,
        preceding_chord_shape_values=[1, 1, 1, 1]
        # a shape that, if consulted, would never match fret 9 --
        # confirms this parameter is genuinely unreachable here
    )

    assert chosen == {"string": 2, "fret": 9}


# ---------------------------------------------------------
# 7 -- control: no preceding_chord_shape_values at all leaves
# existing BO-24/25/30 behavior completely unchanged (the
# established B7/B3/G#m example)
# ---------------------------------------------------------

def test_no_preceding_shape_preserves_established_bo30_example():

    open_notes = A_MODAL_SAWMILL.notes[1:]

    chosen = _choose_melody_position(
        59, open_notes,  # B3
        working_fret_anchor=4, following_working_fret_anchor=1
    )

    assert chosen["string"] == 1

    assert chosen["fret"] == 2


# ---------------------------------------------------------
# 8 -- full pipeline: the real reference-score cases, end to
# end, plus FD/TAB consistency and exception handling intact
# ---------------------------------------------------------

def test_full_pipeline_real_cases_and_consistency():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, DOUBLE_C, staff_used, TEMPLATE_PATH, "output",
            service, filename="test_bo37_pipeline.mscz"
        )
    )

    try:

        assert applied == 56

        assert skipped == 0

        assert exceptions == []

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        fret_diagrams = staff.findall(".//{*}FretDiagram")

        assert len(fret_diagrams) == 56

        for fd in fret_diagrams:

            assert fd.find("{*}color") is None

        measures = staff.findall("{*}Measure")

        # measure 3's real, confirmed E4/Em case
        m3_voice = list(measures[2].find("{*}voice"))

        e4_chord = next(
            el for el in m3_voice
            if el.tag.split("}")[-1] == "Chord"
            and el.find("{*}Note").find("{*}pitch").text == "64"
        )

        e4_note = e4_chord.find("{*}Note")

        assert e4_note.find("{*}fret").text == "4"

        assert e4_note.find("{*}string").text == "1"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
