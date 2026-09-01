"""
tests/test_bo83_chord_aware_rhythmic_retention.py

Regression tests for BO-83: the BO-81 rhythmic candidate filter is
gated off (retaining the full, unfiltered candidate list) whenever
this specific note has an established chord anchor
(working_fret_anchor is not None) -- letting existing, completely
unmodified fret_distance/HP/preceding_fd_violation logic evaluate
a candidate it has already identified as chord-relevant, even when
that candidate is neither rhythm-compatible nor literally inside
the anchor's own HP span.

Real motivating case (BO-82's own investigation): The Christmas
Song, Cmaj7/A4 -- string 2/fret 7 was being discarded by the
rhythmic filter before fret_distance (which correctly favors it,
being close to the established anchor 9) ever got a chance.

Deliberately per-note, not per-song: CSB never has a chord anchor
at all (confirmed chord-less throughout), so this gate never
activates there and BO-81's own rhythmic behavior for it is
completely unaffected.
"""

import sys

sys.path.insert(0, '.')

from score_generator import _choose_melody_position

from tunings import get_tunings

from hand_position import HandPosition

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


DOUBLE_D = get_tunings()["Double D"]

DOUBLE_C = get_tunings()["Double C"]

C_STANDARD = get_tunings()["C Standard"]


# ---------------------------------------------------------
# 1 -- real Cmaj7/A4 case: chord anchor present, full
# candidate list retained, fret 7 correctly restored
# ---------------------------------------------------------

def test_chord_anchor_retains_full_candidates_direct():

    open_notes = DOUBLE_D.notes[1:] + [DOUBLE_D.notes[0]]

    result = _choose_melody_position(
        69, open_notes,
        working_fret_anchor=9,
        current_hp=HandPosition(9, 12),
        expected_attack_role="pull"
    )

    # fret 7 is NOT rhythm-compatible with "pull" (only the open
    # 5th string is) and is NOT inside the anchor's own HP span
    # (9,12) either -- it wins purely because the full candidate
    # list was retained and existing, unmodified fret_distance
    # logic correctly favored it (|7-9|=2 vs the 5th string's
    # |0-9|=9).
    assert result["string"] == 2

    assert result["fret"] == 7


# ---------------------------------------------------------
# 2 -- no chord anchor: BO-81's rhythmic filter still applies
# normally, exactly as before BO-83
# ---------------------------------------------------------

def test_no_anchor_rhythmic_filter_still_applies():

    open_notes = DOUBLE_C.notes[1:] + [DOUBLE_C.notes[0]]

    result_pull = _choose_melody_position(
        67, open_notes, expected_attack_role="pull"
    )

    assert result_pull["string"] == 4

    assert result_pull["fret"] == 0

    result_down = _choose_melody_position(
        67, open_notes, expected_attack_role="down"
    )

    assert not (
        result_down["string"] == 4 and result_down["fret"] == 0
    )


# ---------------------------------------------------------
# 3 -- real CSB regression: G4-rest-G4-G4 pattern unaffected
# ---------------------------------------------------------

def test_real_csb_g4_measure_7_still_unaffected():

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
            service, filename="test_bo83_csb_m7.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g4_entries = [
            e for e in trace
            if e.measure == 7 and e.pitch == 67
        ]

        assert len(g4_entries) == 3

        # finger - finger - thumb, unchanged from BO-81.
        assert g4_entries[0].string == 3 and g4_entries[0].fret == 5

        assert g4_entries[1].string == 3 and g4_entries[1].fret == 5

        assert g4_entries[2].string == 4 and g4_entries[2].fret == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4 -- real CSB regression: G4-G4-G4 pattern unaffected
# ---------------------------------------------------------

def test_real_csb_g4_measure_9_still_unaffected():

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
            service, filename="test_bo83_csb_m9.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g4_entries = [
            e for e in trace
            if e.measure == 9 and e.pitch == 67
        ]

        assert len(g4_entries) == 3

        # finger - thumb - finger, unchanged from BO-81.
        assert g4_entries[0].string == 3 and g4_entries[0].fret == 5

        assert g4_entries[1].string == 4 and g4_entries[1].fret == 0

        assert g4_entries[2].string == 3 and g4_entries[2].fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 5 -- real Cmaj7/A4 end-to-end regression
# ---------------------------------------------------------

def test_real_tcs_a4_cmaj7_fret_7_restored():

    import os

    p = MuseScoreFile("scores/The Christmas Song.mscz")

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
            service, filename="test_bo83_tcs_a4.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        a4_entry = next(
            e for e in trace
            if e.measure == 2 and e.pitch == 69
        )

        assert a4_entry.string == 2

        assert a4_entry.fret == 7

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 6 -- fallback: rhythmic filter eliminating every candidate
# still falls back correctly even with retention gate present
# ---------------------------------------------------------

def test_fallback_still_works_with_retention_gate():

    from stroke_cycle import filter_by_attack_role

    candidates = [
        {"string": 2, "fret": 5, "score": 9},
        {"string": 1, "fret": 3, "score": 7},
    ]

    # No genuinely open 5th-string candidate exists -- filter
    # must still fall back to the unfiltered list, exactly as in
    # BO-81, regardless of the new BO-83 gate (which only concerns
    # whether the filter runs at all, not its own fallback logic).
    result = filter_by_attack_role(candidates, "pull")

    assert result == candidates
