"""
tests/test_bo59_hp_trace_wiring.py

Regression tests for BO-59's real-generation HP wiring
(hp_trace_sink on generate_tab_from_template()). These test that
the ACTUAL event loop -- not just the pure hand_position.py
functions (already covered by test_bo59_hand_position.py's own
21 tests) -- correctly updates and records persistent HP state
during real score generation.
"""

import sys

sys.path.insert(0, '.')

import zipfile

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template

from hand_position import HandPosition


C_STANDARD = get_tunings()["C Standard"]

DOUBLE_C = get_tunings()["Double C"]


def _generate_with_trace(path, tuning, filename):

    p = MuseScoreFile(path)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename=filename, hp_trace_sink=trace
        )
    )

    return output_path, trace


# ---------------------------------------------------------
# hp_trace_sink is purely additive -- existing callers unaffected
# ---------------------------------------------------------

def test_default_call_unaffected_by_hp_trace_sink():

    import os

    p = MuseScoreFile("scores/Cousin Sally Brown.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    # Called exactly as every existing real caller does -- no
    # hp_trace_sink at all. Must still return exactly 4 values.
    result = generate_tab_from_template(
        p, C_STANDARD, staff_used,
        "templates/TAB_linked_Treble_Example.mscz", "output",
        service, filename="test_bo59_no_trace.mscz"
    )

    assert len(result) == 4

    output_path = result[0]

    if os.path.exists(output_path):

        os.remove(output_path)


# ---------------------------------------------------------
# Real CSB/gCGBD wiring: open first note, first fretted note,
# inside/above/below transitions, all through the real event loop
# ---------------------------------------------------------

def test_real_csb_gCGBD_open_first_note_no_hp():

    import os

    output_path, trace = _generate_with_trace(
        "scores/Cousin Sally Brown.mscz", C_STANDARD,
        "test_bo59_trace_gCGBD.mscz"
    )

    try:

        first_note_entries = [
            e for e in trace if e.event_type != "chord"
        ]

        first = first_note_entries[0]

        # Real, confirmed: the real first melody note (G3) is an
        # open string.
        assert first.event_type == "open_note"

        assert first.hp_before is None

        assert first.hp_after is None

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_csb_gCGBD_first_fretted_note_establishes_hp():

    import os

    output_path, trace = _generate_with_trace(
        "scores/Cousin Sally Brown.mscz", C_STANDARD,
        "test_bo59_trace_gCGBD2.mscz"
    )

    try:

        fretted_entries = [
            e for e in trace if e.event_type == "fretted_note"
        ]

        first_fretted = fretted_entries[0]

        # Real, confirmed: A3 at fret 2 is the first fretted
        # melody note in Cousin Sally Brown / C Standard.
        assert first_fretted.fret == 2

        assert first_fretted.hp_before is None

        assert first_fretted.hp_after == HandPosition(2, 5)

        assert first_fretted.transition == "established_first"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_csb_gCGBD_fretted_note_inside_hp_unchanged():

    import os

    output_path, trace = _generate_with_trace(
        "scores/Cousin Sally Brown.mscz", C_STANDARD,
        "test_bo59_trace_gCGBD3.mscz"
    )

    try:

        fretted_entries = [
            e for e in trace if e.event_type == "fretted_note"
        ]

        # Real, confirmed: C4 at fret 1 (right after A3@2)
        # establishes a NEW hp (below the just-established (2,5))
        # -- then E4@2 (measure 1's own last note) genuinely
        # stays inside that new (1,4) hp.
        c4 = fretted_entries[1]

        assert c4.fret == 1

        assert c4.transition == "established_new"

        assert c4.hp_after == HandPosition(1, 4)

        e4 = fretted_entries[2]

        assert e4.fret == 2

        assert e4.transition == "unchanged"

        assert e4.hp_before == HandPosition(1, 4)

        assert e4.hp_after == HandPosition(1, 4)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_csb_gCGBD_open_strings_leave_established_hp_unchanged():

    import os

    output_path, trace = _generate_with_trace(
        "scores/Cousin Sally Brown.mscz", C_STANDARD,
        "test_bo59_trace_gCGBD4.mscz"
    )

    try:

        open_entries = [
            e for e in trace if e.event_type == "open_note"
            and e.hp_before is not None
        ]

        assert len(open_entries) > 0

        for entry in open_entries:

            assert entry.hp_before == entry.hp_after

            assert entry.transition == "open_string"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# Real chord-anchored wiring: every chord/FD resets HP, even
# overlapping ones; the 5-fret exception is preserved
# ---------------------------------------------------------

def test_real_tcs_every_chord_resets_hp():

    import os

    p = MuseScoreFile("scores/The Christmas Song.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    double_d = get_tunings()["Double D"]

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, double_d, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo59_trace_tcs.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        chord_entries = [
            e for e in trace
            if e.event_type == "chord"
            and e.chord_lowest_fret is not None
        ]

        assert len(chord_entries) > 0

        # Every single real chord entry is "chord_reset" -- never
        # "unchanged", confirming the rule applies unconditionally
        # even for chords whose own lowest fret overlaps the
        # previous HP.
        for entry in chord_entries:

            assert entry.transition == "chord_reset"

            assert entry.hp_after.low == entry.chord_lowest_fret

        # Real, confirmed overlapping case: measure 1's C chord
        # establishes (10,13); measure 2's Cmaj7 (lowest fret 9,
        # already inside (10,13)) still genuinely resets to
        # (9,12), never merely preserving the prior HP.
        c_chord = chord_entries[0]

        cmaj7_chord = chord_entries[1]

        assert c_chord.hp_after == HandPosition(10, 13)

        assert cmaj7_chord.hp_after == HandPosition(9, 12)

        assert cmaj7_chord.hp_before == HandPosition(10, 13)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_tcs_five_fret_exception_preserved():

    import os

    p = MuseScoreFile("scores/The Christmas Song.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    a_modal_sawmill = get_tunings()["A Modal Sawmill"]

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, a_modal_sawmill, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo59_trace_5fret.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        chord_entries = [
            e for e in trace
            if e.event_type == "chord"
            and e.chord_lowest_fret is not None
        ]

        # Confirmed: no real FD in any of the 4 BO-59 investigation
        # songs spans more than 3 frets -- every real hp_after
        # here is a normal 4-fret window (high - low == 3). This
        # locks in that the rule doesn't accidentally FIRE where
        # it shouldn't; test_bo59_hand_position.py's own unit
        # tests already directly confirm the exception logic
        # itself for a synthetic wide shape.
        for entry in chord_entries:

            assert entry.hp_after.high - entry.hp_after.low == 3

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# The real, motivating CSB/gCGCD case, through the real,
# wired-in production event loop
# ---------------------------------------------------------

def test_real_csb_gCGCD_established_hp_before_g4_is_2_5():

    import os

    output_path, trace = _generate_with_trace(
        "scores/Cousin Sally Brown.mscz", DOUBLE_C,
        "test_bo59_trace_gCGCD.mscz"
    )

    try:

        g4_entries = [
            e for e in trace
            if e.pitch == 67 and e.event_type == "fretted_note"
        ]

        assert len(g4_entries) > 0

        first_g4 = g4_entries[0]

        # Real, confirmed: the established HP immediately before
        # the first G4 (measure 7) is (2,5) -- set at measure 1's
        # own A3 and never genuinely left (the intervening E4@4
        # in measure 6 stays inside it).
        assert first_g4.hp_before == HandPosition(2, 5)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_csb_gCGCD_g4_stays_inside_established_hp():

    import os

    output_path, trace = _generate_with_trace(
        "scores/Cousin Sally Brown.mscz", DOUBLE_C,
        "test_bo59_trace_gCGCD2.mscz"
    )

    try:

        g4_entries = [
            e for e in trace
            if e.pitch == 67 and e.event_type == "fretted_note"
        ]

        first_g4 = g4_entries[0]

        # BO-60, superseding this test's own prior version (which
        # locked in the pre-fix bug): G4's own real candidates at
        # fret 5 and fret 7 genuinely tie on phrase coverage
        # (confirmed real, 3 vs 3) -- with no real phrase-based
        # winner, BO-60's HP tiebreak now correctly prefers fret
        # 5 (inside the established (2,5)) over fret 7 (outside
        # it), rather than falling through to the legacy "favor
        # middle strings" heuristic that previously decided this
        # tie incorrectly.
        assert first_g4.fret == 5

        assert first_g4.transition == "unchanged"

        assert first_g4.hp_after == HandPosition(2, 5)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
