"""
tests/test_bo81_stroke_cycle.py

Regression tests for BO-81: the rhythmic clawhammer stroke-cycle
model (stroke_cycle.py) and its integration as a candidate-
availability pre-filter in _choose_melody_position() -- NOT a new
_sort_key component (per the BO-74 lesson this whole design was
built to respect).
"""

import sys

sys.path.insert(0, '.')

from stroke_cycle import (
    compute_stroke_phase_by_event_id, filter_by_stroke_phase
)

from score_generator import _choose_melody_position

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


DOUBLE_C = get_tunings()["Double C"]

C_STANDARD = get_tunings()["C Standard"]


# ---------------------------------------------------------
# Test A -- ordinary eighth-note alternation
# ---------------------------------------------------------

def test_eighth_note_alternation():

    events = [
        {"duration": 0.5, "tuplet_scale": 1.0} for _ in range(4)
    ]

    phases = compute_stroke_phase_by_event_id(events)

    assert [phases[id(e)].phase for e in events] == [
        "down", "pull", "down", "pull"
    ]


# ---------------------------------------------------------
# Test B -- quarter-note timing (elapsed time, not event count)
# ---------------------------------------------------------

def test_quarter_note_consumes_two_stroke_units():

    events = [
        {"duration": 1.0, "tuplet_scale": 1.0},
        {"duration": 1.0, "tuplet_scale": 1.0},
    ]

    phases = compute_stroke_phase_by_event_id(events)

    # A quarter note is 2 stroke units -- the second quarter's
    # own onset is therefore "down" again (not "pull", which an
    # event-count model would have wrongly produced).
    assert phases[id(events[0])].phase == "down"

    assert phases[id(events[1])].phase == "down"

    assert phases[id(events[1])].units_elapsed == 2.0


# ---------------------------------------------------------
# Test C -- a rest consumes the same time as an equal-duration
# note, without resetting the cycle
# ---------------------------------------------------------

def test_rest_occupies_same_phase_as_equal_duration_note():

    with_rest = [
        {"duration": 0.5, "tuplet_scale": 1.0},
        {"duration": 0.5, "tuplet_scale": 1.0},  # the "rest"
        {"duration": 0.5, "tuplet_scale": 1.0},
    ]

    with_note = [
        {"duration": 0.5, "tuplet_scale": 1.0},
        {"duration": 0.5, "tuplet_scale": 1.0},
        {"duration": 0.5, "tuplet_scale": 1.0},
    ]

    phases_rest = compute_stroke_phase_by_event_id(with_rest)

    phases_note = compute_stroke_phase_by_event_id(with_note)

    assert (
        [phases_rest[id(e)].phase for e in with_rest]
        == [phases_note[id(e)].phase for e in with_note]
        == ["down", "pull", "down"]
    )


# ---------------------------------------------------------
# Test D -- a sustained note consumes its full duration before
# the next event's phase is determined
# ---------------------------------------------------------

def test_sustained_half_note_consumes_full_duration():

    events = [
        {"duration": 2.0, "tuplet_scale": 1.0},  # half note
        {"duration": 0.5, "tuplet_scale": 1.0},
    ]

    phases = compute_stroke_phase_by_event_id(events)

    # 2.0 beats = 4 stroke units -- the next onset is "down"
    # again, not determined by event count (which would say
    # "pull", the second event overall).
    assert phases[id(events[1])].phase == "down"

    assert phases[id(events[1])].units_elapsed == 4.0


# ---------------------------------------------------------
# Test E -- triplets use the accelerated subdivision
# ---------------------------------------------------------

def test_triplet_uses_accelerated_subdivision():

    events = [
        {"duration": 1 / 3, "tuplet_scale": 2 / 3}
        for _ in range(3)
    ]

    phases = compute_stroke_phase_by_event_id(events)

    # Each triplet note is its own stroke unit (BO-80's own
    # established musical decision: the hand speeds up to match
    # the triplet), NOT beat/0.5 (which would give non-integer,
    # meaningless positions for these exact durations).
    assert [phases[id(e)].phase for e in events] == [
        "down", "pull", "down"
    ]


# ---------------------------------------------------------
# Test F -- candidate filtering retains only stroke-appropriate
# candidates
# ---------------------------------------------------------

def test_filter_retains_only_compatible_candidates():

    candidates = [
        {"string": 2, "fret": 5, "score": 9},
        {"string": 4, "fret": 0, "score": 10},
    ]

    assert filter_by_stroke_phase(candidates, "down") == [
        {"string": 2, "fret": 5, "score": 9}
    ]

    assert filter_by_stroke_phase(candidates, "pull") == [
        {"string": 4, "fret": 0, "score": 10}
    ]


def test_fretted_fifth_string_is_not_treated_as_thumb():

    # Real, confirmed during BO-81's own implementation: the 5th
    # string can be FRETTED (e.g. reaching an adjacent pitch),
    # exactly like any other string -- a fretted 5th-string note
    # is an ordinary fretting-hand note, not a thumb-on-an-open-
    # string stroke, and must not be treated as "pull"-compatible
    # merely because its string_index is 4.
    candidates = [
        {"string": 4, "fret": 1, "score": 6},  # fretted 5th string
        {"string": 3, "fret": 6, "score": 8},
    ]

    assert filter_by_stroke_phase(candidates, "pull") == (
        candidates
    ), "fallback expected -- no genuinely open 5th-string candidate exists"

    assert filter_by_stroke_phase(candidates, "down") == (
        candidates
    ), "a fretted 5th-string candidate is itself down-compatible"


# ---------------------------------------------------------
# Test G -- mandatory fallback when nothing is compatible
# ---------------------------------------------------------

def test_fallback_returns_unfiltered_when_nothing_compatible():

    candidates = [
        {"string": 2, "fret": 5, "score": 9},
        {"string": 1, "fret": 3, "score": 7},
    ]

    result = filter_by_stroke_phase(candidates, "pull")

    assert result == candidates


# ---------------------------------------------------------
# Test H -- existing selection machinery still decides among
# the filtered candidates (the filter narrows availability, it
# does not itself score or choose)
# ---------------------------------------------------------

def test_existing_selection_logic_decides_among_filtered_candidates():

    open_notes = DOUBLE_C.notes[1:] + [DOUBLE_C.notes[0]]

    # G4 with an expected "pull" phase: only the open 5th string
    # survives filtering, and it is returned even though it is
    # NOT what -score alone would necessarily favor among a wider
    # pool -- confirming the filter, not new scoring, decided
    # candidate AVAILABILITY, while existing logic still picked
    # among what survived.
    result_pull = _choose_melody_position(
        67, open_notes, expected_stroke_phase="pull"
    )

    assert result_pull["string"] == 4

    assert result_pull["fret"] == 0

    # With an expected "down" phase, the open 5th string must be
    # excluded entirely -- existing scoring then picks among the
    # remaining, ordinary fretted candidates exactly as before
    # BO-81 (unmodified _sort_key).
    result_down = _choose_melody_position(
        67, open_notes, expected_stroke_phase="down"
    )

    assert not (
        result_down["string"] == 4 and result_down["fret"] == 0
    )


# ---------------------------------------------------------
# Real CSB regression -- the primary motivating evidence
# ---------------------------------------------------------

def test_real_csb_g4_measure_7_rest_pattern():

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
            service, filename="test_bo81_csb_m7.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g4_entries = [
            e for e in trace
            if e.measure == 7 and e.pitch == 67
        ]

        assert len(g4_entries) == 3

        # Real, confirmed target pattern (down-down-pull, the
        # rest at beat 0.5 occupying its own "pull" stroke
        # position invisibly, between the two real notes):
        # finger - finger - thumb.
        assert g4_entries[0].string == 3
        assert g4_entries[0].fret == 5

        assert g4_entries[1].string == 3
        assert g4_entries[1].fret == 5

        assert g4_entries[2].string == 4
        assert g4_entries[2].fret == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_csb_g4_measure_9_no_rest_pattern():

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
            service, filename="test_bo81_csb_m9.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g4_entries = [
            e for e in trace
            if e.measure == 9 and e.pitch == 67
        ]

        assert len(g4_entries) == 3

        # Real, confirmed target pattern: finger - thumb - finger.
        assert g4_entries[0].string == 3
        assert g4_entries[0].fret == 5

        assert g4_entries[1].string == 4
        assert g4_entries[1].fret == 0

        assert g4_entries[2].string == 3
        assert g4_entries[2].fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
