"""
tests/test_bo24_melody_position_anchoring.py

Regression tests for BO-24: use the selected FretDiagram as a
positional anchor for TAB realization, so generated melody
positions better reflect the chord shapes BO already selected,
and flow more naturally into and out of each chord.

Two layers, both exercised here:

1. _choose_melody_position() (score_generator.py) -- the core,
   reusable decision function. Reuses fretboard.find_positions()/
   best_position() unmodified as the actual candidate source/
   scorer -- this only adds a priority layer on top:
   - fd_shape_values: when the exact melody pitch is one of an
     already-selected chord shape's own positions, that position
     is STRONGLY preferred (returned directly).
   - working_fret_anchor: a nearby chord's own
     playing_model._chord_working_fret() (reused unmodified),
     used as a CAPPED distance tiebreak among find_positions()'s
     own candidates -- never an unbounded pull, matching the
     task's own explicit warning against blindly forcing
     everything toward the next chord.

2. generate_tab_from_template()'s own wiring of the above into
   the real, end-to-end generation pipeline -- confirmed against
   the actual full Christmas Song, not just the isolated
   decision function.

All FD values and expected positions below are taken directly
from the real supplied sample score and the real generation
output, not invented -- see the BO-24 investigation notes for
how each was traced and confirmed.
"""

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from fretboard import parse_shape

from playing_model import _chord_working_fret

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import (
    _choose_melody_position,
    _fd_positions_for_pitch,
    generate_tab_from_template,
    MELODY_ANCHOR_DISTANCE_CAP
)


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

OPEN_NOTES = A_MODAL_SAWMILL.notes[1:]  # 4th to 1st


# ---------------------------------------------------------
# 1 -- an exact melody pitch selecting an FD-compatible
# position
# ---------------------------------------------------------

def test_exact_melody_pitch_selects_fd_compatible_position():

    # Real Cmaj7 FD from the sample score: 0-(10)-9-8. The
    # melody note B4 is only available at ONE position within
    # this shape (fretboard string_index=2, fret=9) -- every
    # other position sounds a different chord tone.
    cmaj7_fd_values = parse_shape("0(10)98")

    chosen = _choose_melody_position(
        71, OPEN_NOTES, fd_shape_values=cmaj7_fd_values
    )

    assert chosen == {"string": 2, "fret": 9}


# ---------------------------------------------------------
# 2 -- open-string FD positions are valid candidates
# ---------------------------------------------------------

def test_open_string_fd_position_is_valid_candidate():

    # Real Em FD from the sample score: 0-2-5-0. E4 is
    # available at fret 0 (open, string_index=3) within this
    # shape -- confirms an open-string FD position is preferred
    # just like any other, not skipped or treated specially.
    em_fd_values = parse_shape("0250")

    chosen = _choose_melody_position(
        64, OPEN_NOTES, fd_shape_values=em_fd_values
    )

    assert chosen == {"string": 3, "fret": 0}

    # Direct check on the lower-level helper too: it must find
    # the open-string match explicitly, not skip fret=0 as if
    # it were "no value."
    matches = _fd_positions_for_pitch(em_fd_values, OPEN_NOTES, 64)

    assert (3, 0) in matches


# ---------------------------------------------------------
# 3 -- a preceding melody note approaches the chord naturally
# ---------------------------------------------------------

def test_preceding_note_approaches_chord_naturally():

    # Real first-C FD from the sample score: 0-(10)-(10)-0,
    # working fret 10. The real preceding melody note is C4,
    # which the un-anchored generator placed at fret 3
    # (string_index=1) -- with the anchor, it should move to
    # fret 8 (string_index=0), the position closest to 10.
    c_fd_values = parse_shape("0(10)(10)0")

    working_fret = _chord_working_fret(c_fd_values)

    assert working_fret == 10

    chosen = _choose_melody_position(
        60, OPEN_NOTES, working_fret_anchor=working_fret
    )

    assert chosen["string"] == 0

    assert chosen["fret"] == 8


# ---------------------------------------------------------
# 4 -- a following melody note leaves the chord naturally
# ---------------------------------------------------------

def test_following_note_leaves_chord_naturally():

    # Same first-C chord (working fret 10). G4's own candidates
    # in aEADE are frets 15/10/5/3 (no open-string option) --
    # anchored to working fret 10, the fret=10 candidate is an
    # EXACT match (distance 0) and should win, even though
    # best_position() alone (with no anchor) prefers fret=3.
    c_fd_values = parse_shape("0(10)(10)0")

    working_fret = _chord_working_fret(c_fd_values)

    chosen = _choose_melody_position(
        67, OPEN_NOTES, working_fret_anchor=working_fret
    )

    assert chosen["fret"] == 10

    assert chosen["string"] == 1

    unanchored = _choose_melody_position(67, OPEN_NOTES)

    assert unanchored["fret"] == 3, (
        "sanity check: confirms this test genuinely exercises "
        "the anchoring logic -- the un-anchored default really "
        "is different from the anchored choice"
    )


# ---------------------------------------------------------
# 5 -- a large change between successive chord positions is
# handled as a transition, not an abrupt forced jump
# ---------------------------------------------------------

def test_large_chord_position_change_is_capped_not_forced():

    # An anchor very far from every available candidate must
    # not force an unreasonable choice -- the distance is
    # capped (MELODY_ANCHOR_DISTANCE_CAP), so beyond that cap
    # every remaining candidate is equally "far" and
    # best_position()'s own score decides among them, exactly
    # like the un-anchored case.
    far_anchor = 19  # deliberately unrealistic distance

    chosen = _choose_melody_position(
        64, OPEN_NOTES, working_fret_anchor=far_anchor
    )

    unanchored = _choose_melody_position(64, OPEN_NOTES)

    assert chosen == unanchored, (
        "an anchor far beyond the cap must not override "
        "best_position()'s own preference -- the cap should "
        "make every candidate equally (maximally) far, letting "
        "the existing playability score decide as usual"
    )

    # Confirm the cap itself is actually finite and reasonable
    # (not accidentally disabled).
    assert MELODY_ANCHOR_DISTANCE_CAP < far_anchor


# ---------------------------------------------------------
# 6 -- existing behavior remains intact when no useful
# alternative string/fret exists
# ---------------------------------------------------------

def test_no_fd_match_and_no_anchor_falls_back_unchanged():

    # A shape that does not contain this pitch anywhere --
    # falls through to plain best_position(), completely
    # unaffected by the (irrelevant) fd_shape_values.
    unrelated_fd_values = parse_shape("0250")  # Em, no C5 in it

    with_irrelevant_fd = _choose_melody_position(
        72, OPEN_NOTES, fd_shape_values=unrelated_fd_values
    )

    plain = _choose_melody_position(72, OPEN_NOTES)

    assert with_irrelevant_fd == plain

    # No anchors at all -- must be identical to calling
    # find_positions()/best_position() directly, unchanged.
    from fretboard import find_positions, best_position

    positions = find_positions(72, OPEN_NOTES)

    expected = best_position(positions)

    assert _choose_melody_position(72, OPEN_NOTES) == expected


# ---------------------------------------------------------
# 7 -- full pipeline: the three real examples from the
# supplied sample score, confirmed in the actual generated
# output, not just the isolated decision function
# ---------------------------------------------------------

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"


def _note_fret_string(voice_children, index):

    note = voice_children[index].find("{*}Note")

    fret = int(note.find("{*}fret").text)

    ms_string = int(note.find("{*}string").text)

    return fret, ms_string


def test_full_pipeline_matches_all_three_real_examples():

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
            "output",
            service,
            filename="test_bo24_full_pipeline.mscz"
        )
    )

    import os

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        measures = staff.findall("{*}Measure")

        # Measure 1's only note: C4, expected fret=8 string=3
        # (player-facing "4-8"). Voice children:
        # KeySig, TimeSig, Rest, Rest, Chord.
        m1_voice = list(measures[0].find("{*}voice"))

        fret, ms_string = _note_fret_string(m1_voice, 4)

        assert (fret, ms_string) == (8, 3)

        # Measure 2's Cmaj7 onset note (B4): expected fret=9
        # string=1 (player-facing "2-9").
        m2_voice = list(measures[1].find("{*}voice"))

        # Harmony, FretDiagram, Chord(C5), Harmony, FretDiagram,
        # Chord(B4) -- index 5 is the Cmaj7 onset Chord.
        fret, ms_string = _note_fret_string(m2_voice, 5)

        assert (fret, ms_string) == (9, 1)

        # Every Em occurrence (measures 2, 13, 29 -- "middle"
        # and "final" both included) selects fret=0 string=0
        # (player-facing "1-0") for its own onset note.
        em_measure_indices_with_onset_offset = [
            (1, 11),   # measure 2: Harmony, FretDiagram, Chord,
                       # Harmony, FretDiagram, Chord, Chord,
                       # Chord, Chord, Harmony, FretDiagram,
                       # Chord(E4) -- index 11
            (12, 8),   # measure 13
            (28, 8),   # measure 29 ("final Em")
        ]

        for mi, onset_offset in em_measure_indices_with_onset_offset:

            voice_children = list(
                measures[mi].find("{*}voice")
            )

            fret, ms_string = _note_fret_string(
                voice_children, onset_offset
            )

            assert (fret, ms_string) == (0, 0), (
                f"measure {mi + 1}'s Em onset note: expected "
                f"fret=0 string=0, got fret={fret} "
                f"string={ms_string}"
            )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
