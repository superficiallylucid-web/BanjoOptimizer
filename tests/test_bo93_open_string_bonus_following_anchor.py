"""
tests/test_bo93_open_string_bonus_following_anchor.py

Regression tests for BO-93: open_string_bonus now also requires
following_working_fret_anchor is not None, restoring the mechanism
to its own originally documented purpose (BO-38 Group A: protect
an open-string candidate from a FOLLOWING chord anchor's pull) --
a check the original implementation never actually performed.

Real motivating cases (BO-92's own direct investigation):

- The Christmas Song, C4, measure 1, beat 2.5, duration 1.5 beats
  (role=None -- ineligible) -- genuinely HAS a following chord
  anchor (following_working_fret_anchor=7) and must continue
  selecting the open string.

- The Rhythmic Clawhammer Stroke Cycle score's own long notes
  (measures 3/4/7/8, all role=None) -- entirely chord-less, never
  have a following anchor at all, and must NOT receive the open
  5th string solely because of open_string_bonus.
"""

import sys

sys.path.insert(0, '.')

from score_generator import _choose_melody_position

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


DOUBLE_C = get_tunings()["Double C"]

C_STANDARD = get_tunings()["C Standard"]


# ---------------------------------------------------------
# 1 -- real Christmas Song C4 case: following anchor present,
# open string continues to win
# ---------------------------------------------------------

def test_real_christmas_song_c4_still_selects_open_string():

    import os

    p = MuseScoreFile(
        "The Christmas Song (notation only).mscz"
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
            p, DOUBLE_C, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo93_c4.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        c4_entry = next(
            e for e in trace
            if e.measure == 1 and e.pitch == 60
        )

        # Real, confirmed: string 2/fret 0, the open string --
        # a genuine following chord anchor (the "C" chord)
        # continues to justify this selection.
        assert c4_entry.string == 2

        assert c4_entry.fret == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 2 -- real controlled-score long notes: no following anchor,
# open_string_bonus alone no longer forces the 5th string
# ---------------------------------------------------------

def test_real_controlled_score_long_notes_no_longer_forced_open():

    import os

    p = MuseScoreFile("Rhythmic_Clawhammer_Stroke_Cycle.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, C_STANDARD, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo93_rcsc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        def is_fifth_string(e):

            return e.string == 4 and e.fret == 0

        # Real, confirmed: every long-note (>1 beat, role=None)
        # occurrence in this entirely chord-less score -- none of
        # them ever has a following chord anchor at all -- no
        # longer selects the open 5th string.
        long_note_positions = [
            (3, 0.0), (3, 2.0),
            (4, 0.0), (4, 2.0),
            (7, 0.0),
            (8, 0.0), (8, 1.5),
        ]

        by_measure_beat = {
            (e.measure, e.beat): e for e in trace
            if e.event_type != "rest"
        }

        for key in long_note_positions:

            entry = by_measure_beat[key]

            assert not is_fifth_string(entry), (
                f"{key}: still selecting the open 5th string"
            )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- existing BO-88 eligible down/pull behavior unaffected
# ---------------------------------------------------------

def test_eligible_pull_attack_still_selects_open_string():

    open_notes = DOUBLE_C.notes[1:] + [DOUBLE_C.notes[0]]

    # An eligible "pull" attack (role is not None) is completely
    # unaffected by this change -- the filter_by_attack_role()
    # mechanism (BO-88, untouched) already narrows candidates to
    # only the open 5th string for a pull role, independent of
    # open_string_bonus entirely.
    result = _choose_melody_position(
        67, open_notes, expected_attack_role="pull"
    )

    assert result["string"] == 4

    assert result["fret"] == 0


def test_eligible_down_attack_unaffected():

    open_notes = DOUBLE_C.notes[1:] + [DOUBLE_C.notes[0]]

    result = _choose_melody_position(
        67, open_notes, expected_attack_role="down"
    )

    assert not (
        result["string"] == 4 and result["fret"] == 0
    )


def test_real_csb_g4_clawhammer_pattern_unaffected():

    import os

    p = MuseScoreFile("scores/Cousin Sally Brown.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, C_STANDARD, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo93_csb_g4.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        # Real, confirmed: the primary, already-validated
        # finger-thumb-finger clawhammer pattern (BO-88's own
        # central achievement) remains completely intact -- G4's
        # own eligible "pull" selections never depended on
        # open_string_bonus at all (only one candidate -- the
        # open string itself -- ever survives BO-88's own filter
        # for a pull role), so this change cannot affect them.
        g4_entries = [
            e for e in trace
            if e.measure == 9 and e.pitch == 67
        ]

        assert len(g4_entries) == 3

        assert g4_entries[0].string == 3 and g4_entries[0].fret == 5

        assert g4_entries[1].string == 4 and g4_entries[1].fret == 0

        assert g4_entries[2].string == 3 and g4_entries[2].fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
