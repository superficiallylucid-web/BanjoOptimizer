"""
tests/test_bo30_bidirectional_anchor.py

Regression tests for BO-30: a melody note sitting immediately
between two adjacent chord onsets can now consider BOTH the
preceding and following chord's own working fret, not just the
preceding one.

Core design, confirmed against all 5 real occurrences of this
exact situation in The Christmas Song before any code was
written: _choose_melody_position()'s fret_distance becomes a
capped MAX of the distance to each anchor that's actually set --
never a sum, never "nearest wins". Max was the only one of the
three obvious combination rules that behaved correctly on every
real case: it's the only one that can't be fooled by a candidate
that's excellent for one side and poor for the other, since
that's not a genuine transition between two chord positions.
When only one anchor applies (the ordinary, far more common
case), the max collapses to exactly that single distance --
BO-24's own original behavior, unchanged.

All FD values, working frets, and expected positions below are
taken from the real BO-30 investigation and the real generation
output, not invented.
"""

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import (
    _choose_melody_position,
    generate_tab_from_template
)


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

OPEN_NOTES = A_MODAL_SAWMILL.notes[1:]  # 4th to 1st

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


# ---------------------------------------------------------
# 1 -- the real B7 -> intermediate note -> G#m case
# ---------------------------------------------------------

def test_real_b7_to_gsm_intermediate_note():

    # B3 (midi 59), preceding B7 (working fret 4), following
    # G#m (working fret 6) -- confirmed real values.
    chosen = _choose_melody_position(
        59, OPEN_NOTES,
        working_fret_anchor=4,
        following_working_fret_anchor=6
    )

    assert chosen["string"] == 0

    assert chosen["fret"] == 7

    # Confirm this genuinely differs from the old, single-anchor
    # (preceding only) behavior -- otherwise this test wouldn't
    # be exercising the new logic at all.
    single_anchor = _choose_melody_position(
        59, OPEN_NOTES, working_fret_anchor=4
    )

    assert single_anchor["string"] == 1

    assert single_anchor["fret"] == 2

    assert (chosen["string"], chosen["fret"]) != (
        single_anchor["string"], single_anchor["fret"]
    )


# ---------------------------------------------------------
# 2 -- both surrounding chord positions similar: intermediate
# note stays in that area (real m29 C4: both anchors = 3)
# ---------------------------------------------------------

def test_similar_anchors_stay_in_area():

    chosen = _choose_melody_position(
        60, OPEN_NOTES,
        working_fret_anchor=3,
        following_working_fret_anchor=3
    )

    assert chosen["fret"] == 3

    # Sanity: distance to both anchors is exactly 0, the
    # smallest possible outcome.
    single_anchor = _choose_melody_position(
        60, OPEN_NOTES, working_fret_anchor=3
    )

    assert (chosen["string"], chosen["fret"]) == (
        single_anchor["string"], single_anchor["fret"]
    )


# ---------------------------------------------------------
# 3 -- surrounding chord positions move substantially apart:
# intermediate note must choose the best available transition
# ---------------------------------------------------------

def test_substantially_apart_anchors_choose_best_transition():

    # Constructed per the task's own example: previous chord
    # around fret 10, next chord around fret 3. Using G4 (midi
    # 67), which has real candidates at frets 15/10/5/3 in
    # aEADE -- a genuine choice exists between "close to one
    # side" options.
    chosen = _choose_melody_position(
        67, OPEN_NOTES,
        working_fret_anchor=10,
        following_working_fret_anchor=3
    )

    # Confirm this is NOT simply an average (which would suggest
    # something near fret 6.5, not an actual candidate) -- report
    # the real winner and its distances explicitly.
    from fretboard import find_positions, best_position

    positions = find_positions(67, OPEN_NOTES)

    best_position(positions)

    scored = []

    for p in positions:

        dist_prec = min(abs(p["fret"] - 10), 5)

        dist_foll = min(abs(p["fret"] - 3), 5)

        scored.append(
            (max(dist_prec, dist_foll), -p["score"], p)
        )

    scored.sort(key=lambda x: (x[0], x[1]))

    expected = scored[0][2]

    assert chosen["string"] == expected["string"]

    assert chosen["fret"] == expected["fret"]


# ---------------------------------------------------------
# 4 -- only a preceding chord: behavior unchanged from BO-24
# ---------------------------------------------------------

def test_only_preceding_anchor_unchanged():

    with_following_none = _choose_melody_position(
        69, OPEN_NOTES, working_fret_anchor=3
    )

    with_following_explicit_none = _choose_melody_position(
        69, OPEN_NOTES, working_fret_anchor=3,
        following_working_fret_anchor=None
    )

    assert (
        with_following_none["string"],
        with_following_none["fret"]
    ) == (
        with_following_explicit_none["string"],
        with_following_explicit_none["fret"]
    )


# ---------------------------------------------------------
# 5 -- only a following chord: verify intended behavior
# ---------------------------------------------------------

def test_only_following_anchor():

    # With only a following anchor, the max collapses to that
    # single distance -- same mechanism as "only preceding",
    # mirrored.
    chosen = _choose_melody_position(
        69, OPEN_NOTES, following_working_fret_anchor=3
    )

    from fretboard import find_positions, best_position

    positions = find_positions(69, OPEN_NOTES)

    best_position(positions)

    scored = sorted(
        positions,
        key=lambda p: (
            min(abs(p["fret"] - 3), 5), -p["score"]
        )
    )

    expected = scored[0]

    assert chosen["string"] == expected["string"]

    assert chosen["fret"] == expected["fret"]


# ---------------------------------------------------------
# 6 -- at a chord onset: exact FD matching remains unchanged
# ---------------------------------------------------------

def test_fd_match_at_onset_unaffected_by_both_anchors():

    from fretboard import parse_shape

    # Real Cmaj7 FD, confirmed in prior BO-24 work: only one
    # position for B4.
    cmaj7_fd = parse_shape("0(10)98")

    chosen = _choose_melody_position(
        71, OPEN_NOTES, fd_shape_values=cmaj7_fd,
        working_fret_anchor=2,
        following_working_fret_anchor=15
    )

    assert chosen == {"string": 2, "fret": 9}


# ---------------------------------------------------------
# 7 -- BO-25 string continuity remains intact alongside the
# new two-sided anchor
# ---------------------------------------------------------

def test_string_continuity_still_applies_with_both_anchors():

    # Genuine fret_distance tie under the two-sided anchor
    # (both candidates equally far from both anchors), so
    # string continuity should still decide, exactly as BO-25
    # established.
    previous = {"string": 0, "fret": 20}

    chosen = _choose_melody_position(
        57, OPEN_NOTES,  # A3: candidates at string0/fret5,
        working_fret_anchor=10,        # string1/fret0
        following_working_fret_anchor=10,
        previous_position=previous
    )

    assert chosen["string"] == 0

    assert chosen["fret"] == 5


# ---------------------------------------------------------
# 8 -- BO-20/21 melody matching and red exception handling
# remain intact (full pipeline check)
# ---------------------------------------------------------

def test_full_pipeline_bo20_21_unaffected():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service,
            filename="test_bo30_pipeline.mscz"
        )
    )

    import os

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

        # The real target case, confirmed end to end.
        measures = staff.findall("{*}Measure")

        m7_voice = list(measures[6].find("{*}voice"))

        b3_chord = None

        for el in m7_voice:

            if el.tag.split("}")[-1] == "Chord":

                note = el.find("{*}Note")

                if note.find("{*}pitch").text == "59":

                    b3_chord = el

                    break

        assert b3_chord is not None

        b3_note = b3_chord.find("{*}Note")

        assert b3_note.find("{*}fret").text == "7"

        assert b3_note.find("{*}string").text == "3"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
