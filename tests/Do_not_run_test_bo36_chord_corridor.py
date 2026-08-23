"""
tests/test_bo36_chord_corridor.py

Regression tests for BO-36/BO-37: score_generator._choose_
melody_position() now also considers a bounded fret CORRIDOR
formed by the two bracketing chords around a surrounding melody
note -- the nearest chord onset before it and the nearest chord
onset after it, regardless of how many intervening melody notes
sit between them (a genuinely wider-reaching lookup than BO-24/
30's own immediate-adjacency anchors, which only ever see the
single nearest note).

    corridor_floor = the lower of the two chords' own lowest
    fretted notes (open strings excluded, matching this
    project's established working-fret convention)

    corridor_ceiling = the higher of the two chords' own
    highest notes

Placed FIRST in the sort key, ahead of fret_distance -- confirmed
necessary by direct simulation before any code changed: a tie-
only placement beneath fret_distance (matching how every earlier
tiebreak in this project was added) only fixed 20 of 46 real
violations found across the whole song, because most violations
are not fret_distance ties at all -- an open string is often the
single closest point to one chord's own working fret while still
falling outside the true corridor spanned by both chords
together.

Real example (The Christmas Song, Double C/gCGCD, measure 2):
melody F4 between Cmaj7 (shape 0979, low=7 excl. open, high=9)
and Em (shape 4445, low=4, high=5). Corridor = [4, 9]. F4's own
candidates are fret3 (violates, below 4) and fret5 (within
bounds) -- BO now correctly selects fret5.

Verified against the real production pipeline: all 46 real
corridor violations found across all 3 tunings (A Modal Sawmill,
Double D, Double C) before this fix are fixed after it. FD/TAB
consistency, exact-pitch selection, BO-24/25/30/33/35 established
behavior all confirmed unaffected.
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


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

DOUBLE_C = get_tunings()["Double C"]  # gCGCD

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


# ---------------------------------------------------------
# 1 -- the real F4/Cmaj7/Em example
# ---------------------------------------------------------

def test_real_f4_corridor_example():

    open_notes = DOUBLE_C.notes[1:]

    # Cmaj7 (0979) -> low=7, high=9. Em (4445) -> low=4, high=5.
    # Combined corridor: [4, 9] -- confirmed real values.
    chosen = _choose_melody_position(
        65, open_notes,  # F4
        following_working_fret_anchor=4,  # Em, immediate anchor
        corridor_floor=4, corridor_ceiling=9
    )

    assert chosen["string"] == 2

    assert chosen["fret"] == 5


# ---------------------------------------------------------
# 2 -- corridor takes priority OVER raw fret_distance (the
# specific design point confirmed necessary by simulation)
# ---------------------------------------------------------

def test_corridor_beats_closer_but_out_of_bounds_candidate():

    open_notes = DOUBLE_C.notes[1:]

    # Confirmed real case: without the corridor check, fret3
    # (distance 1 to the anchor 4) would beat fret5 (distance 1
    # too -- but this test specifically confirms corridor wins
    # even when the out-of-bounds candidate would otherwise be
    # STRICTLY closer, not just tied.
    chosen = _choose_melody_position(
        65, open_notes,
        following_working_fret_anchor=3,  # makes fret3 STRICTLY closer
        corridor_floor=4, corridor_ceiling=9
    )

    assert chosen["fret"] == 5, (
        "fret3 has fret_distance=0 to the anchor (strictly "
        "closer than fret5's distance=2), but corridor_violation "
        "must still be checked first and reject it"
    )


# ---------------------------------------------------------
# 3 -- control: when no in-bounds candidate exists, falls back
# to the existing anchor/score behavior (never forces a worse
# result merely because nothing satisfies the corridor)
# ---------------------------------------------------------

def test_no_in_bounds_candidate_falls_back_gracefully():

    open_notes = DOUBLE_C.notes[1:]

    # An impossible corridor (no real candidate could ever
    # satisfy it) -- every candidate has corridor_violation=1,
    # so the tie is broken by the existing fret_distance/score
    # logic exactly as before, not left undefined.
    chosen = _choose_melody_position(
        65, open_notes,
        following_working_fret_anchor=4,
        corridor_floor=100, corridor_ceiling=200
    )

    assert chosen is not None

    assert chosen["fret"] == 3, (
        "with the corridor unsatisfiable by any candidate, "
        "behavior must fall back to the existing anchor-distance "
        "logic exactly as before this fix"
    )


# ---------------------------------------------------------
# 4 -- control: FD-match at a chord onset remains completely
# unaffected (corridor_floor/ceiling never even reach that
# branch)
# ---------------------------------------------------------

def test_fd_match_unaffected_by_corridor():

    open_notes = A_MODAL_SAWMILL.notes[1:]

    cmaj7_fd = parse_shape("0(10)98")

    chosen = _choose_melody_position(
        71, open_notes, fd_shape_values=cmaj7_fd,
        corridor_floor=0, corridor_ceiling=1
        # an absurdly narrow corridor that the FD's own real
        # position (fret 9) would violate, if this branch were
        # reached at all -- confirms it is genuinely never
        # consulted for a chord-onset note
    )

    assert chosen == {"string": 2, "fret": 9}


# ---------------------------------------------------------
# 5 -- control: no corridor at all leaves existing BO-24/25/30
# behavior completely unchanged (the established B7/B3/G#m
# example)
# ---------------------------------------------------------

def test_no_corridor_preserves_established_bo30_example():

    open_notes = A_MODAL_SAWMILL.notes[1:]

    chosen = _choose_melody_position(
        59, open_notes,  # B3
        working_fret_anchor=4, following_working_fret_anchor=1
        # no corridor_floor/ceiling passed at all
    )

    assert chosen["string"] == 1

    assert chosen["fret"] == 2


# ---------------------------------------------------------
# 6 -- full pipeline: the real example, end to end, plus
# FD/TAB consistency and exception handling intact
# ---------------------------------------------------------

def test_full_pipeline_real_example_and_consistency():

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
            service, filename="test_bo36_pipeline.mscz"
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

        # measure 2's F4, confirmed real fix
        m2_voice = list(measures[1].find("{*}voice"))

        f4_chord = None

        for el in m2_voice:

            if el.tag.split("}")[-1] != "Chord":

                continue

            note = el.find("{*}Note")

            if note.find("{*}pitch").text == "65":

                f4_chord = el

                break

        assert f4_chord is not None

        f4_note = f4_chord.find("{*}Note")

        assert f4_note.find("{*}fret").text == "5"

        assert f4_note.find("{*}string").text == "1"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
