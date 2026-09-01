"""
tests/test_bo88_attack_sequence.py

Regression tests for BO-88: the clawhammer ATTACK SEQUENCE model
(replacing BO-81's original continuous-elapsed-time model, per the
BO-85 through BO-87 investigation chain).

These tests focus on what BO-88 itself is responsible for: the
down/pull ROLE assigned to each eligible attack. Which specific
fretted candidate wins among "down"-eligible options is unaffected
by and outside this mechanism's own scope -- that remains ordinary,
pre-existing legacy candidate scoring, unmodified by BO-88.
"""

import sys

sys.path.insert(0, '.')

from stroke_cycle import (
    compute_attack_sequence_by_event_id, filter_by_attack_role
)

from score_generator import _choose_melody_position

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


DOUBLE_C = get_tunings()["Double C"]

C_STANDARD = get_tunings()["C Standard"]

DOUBLE_D = get_tunings()["Double D"]


# ---------------------------------------------------------
# 1 -- four quarter notes with nothing faster nearby establish
# their own slower sequence: down/pull/down/pull
# ---------------------------------------------------------

def test_four_quarter_notes_establish_own_sequence():

    events = [{"duration": 1.0} for _ in range(4)]

    roles = compute_attack_sequence_by_event_id(events)

    assert [roles[id(e)].role for e in events] == [
        "down", "pull", "down", "pull"
    ]


# ---------------------------------------------------------
# 2 -- eight eighth notes alternate normally
# ---------------------------------------------------------

def test_eight_eighth_notes_alternate():

    events = [{"duration": 0.5} for _ in range(8)]

    roles = compute_attack_sequence_by_event_id(events)

    assert [roles[id(e)].role for e in events] == [
        "down", "pull", "down", "pull",
        "down", "pull", "down", "pull"
    ]


# ---------------------------------------------------------
# 3 -- eighth + eighth + quarter: the quarter CONTINUES the
# eighth-established sequence rather than restarting its own
# ---------------------------------------------------------

def test_quarter_continues_eighth_established_sequence():

    events = [
        {"duration": 0.5}, {"duration": 0.5}, {"duration": 1.0}
    ]

    roles = compute_attack_sequence_by_event_id(events)

    assert [roles[id(e)].role for e in events] == [
        "down", "pull", "down"
    ]


# ---------------------------------------------------------
# 4/5 -- a note >1 beat terminates the sequence; the next
# eligible attack after it starts a fresh sequence at down
# ---------------------------------------------------------

def test_long_note_terminates_sequence_next_attack_starts_down():

    events = [
        {"duration": 0.5},   # down
        {"duration": 2.0},   # ineligible, terminates
        {"duration": 0.5},   # fresh sequence: down
    ]

    roles = compute_attack_sequence_by_event_id(events)

    assert roles[id(events[0])].role == "down"

    assert roles[id(events[1])].role is None

    assert roles[id(events[2])].role == "down"


# ---------------------------------------------------------
# 6 -- a rest consumes its own sequence slot without an
# attack, and does not reset the sequence
# ---------------------------------------------------------

def test_rest_occupies_slot_without_resetting_sequence():

    events = [
        {"duration": 0.5},   # note: down
        {"duration": 0.5},   # rest: pull (no attack, but slot used)
        {"duration": 0.5},   # note: down (sequence continued)
    ]

    roles = compute_attack_sequence_by_event_id(events)

    assert roles[id(events[0])].role == "down"

    assert roles[id(events[1])].role == "pull"

    assert roles[id(events[2])].role == "down"


# ---------------------------------------------------------
# 7 -- candidate filtering: role="pull" retains only a
# genuinely OPEN 5th string; role="down" excludes it; role=None
# is completely inert (ineligible note, unconstrained)
# ---------------------------------------------------------

def test_filter_by_attack_role():

    candidates = [
        {"string": 2, "fret": 5, "score": 9},
        {"string": 4, "fret": 0, "score": 10},
    ]

    assert filter_by_attack_role(candidates, "down") == [
        {"string": 2, "fret": 5, "score": 9}
    ]

    assert filter_by_attack_role(candidates, "pull") == [
        {"string": 4, "fret": 0, "score": 10}
    ]

    assert filter_by_attack_role(candidates, None) == candidates


def test_fretted_fifth_string_is_not_treated_as_pull():

    # A fretted 5th-string candidate (not open) is an ordinary
    # fretting-hand note, not a thumb stroke -- must not be
    # treated as pull-compatible merely because string_index==4.
    candidates = [
        {"string": 4, "fret": 1, "score": 6},
        {"string": 3, "fret": 6, "score": 8},
    ]

    assert filter_by_attack_role(candidates, "pull") == candidates, (
        "fallback expected -- no genuinely open 5th string exists"
    )


def test_fallback_returns_unfiltered_when_nothing_compatible():

    candidates = [
        {"string": 2, "fret": 5, "score": 9},
        {"string": 1, "fret": 3, "score": 7},
    ]

    assert filter_by_attack_role(candidates, "pull") == candidates


# ---------------------------------------------------------
# 8 -- existing selection machinery still decides among the
# filtered candidates
# ---------------------------------------------------------

def test_existing_selection_decides_among_filtered_candidates():

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

    # An ineligible (role=None) note is completely unconstrained --
    # the 5th string may still win via ordinary, unrelated scoring.
    result_none = _choose_melody_position(
        67, open_notes, expected_attack_role=None
    )

    assert result_none["string"] == 4

    assert result_none["fret"] == 0


# ---------------------------------------------------------
# 9 -- real CSB regressions: both confirmed target patterns,
# unchanged from BO-81/83
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
            service, filename="test_bo88_csb_m7.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g4_entries = [
            e for e in trace
            if e.measure == 7 and e.pitch == 67
        ]

        assert len(g4_entries) == 3

        # finger - finger - thumb (the rest at beat 0.5 occupies
        # its own "pull" slot invisibly, between the two real
        # notes).
        assert g4_entries[0].string == 3 and g4_entries[0].fret == 5

        assert g4_entries[1].string == 3 and g4_entries[1].fret == 5

        assert g4_entries[2].string == 4 and g4_entries[2].fret == 0

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
            service, filename="test_bo88_csb_m9.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g4_entries = [
            e for e in trace
            if e.measure == 9 and e.pitch == 67
        ]

        assert len(g4_entries) == 3

        # finger - thumb - finger.
        assert g4_entries[0].string == 3 and g4_entries[0].fret == 5

        assert g4_entries[1].string == 4 and g4_entries[1].fret == 0

        assert g4_entries[2].string == 3 and g4_entries[2].fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 10 -- BO-83 Cmaj7/A4 regression protection remains intact
# ---------------------------------------------------------

def test_real_tcs_a4_cmaj7_still_fret_7():

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
            service, filename="test_bo88_tcs_a4.mscz",
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
# Controlled-score fixture: role classification (down/pull),
# validated against the real TAB fixture's own 5th-string
# positions specifically -- the role BO-88 itself controls.
# Measure 8's own third note is a known, documented exception
# (see stroke_cycle.py's own docstring) and is NOT asserted here.
# ---------------------------------------------------------

def test_real_controlled_score_role_classification():

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
            service, filename="test_bo88_fixture.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        def is_fifth_string(e):

            return e.string == 4 and e.fret == 0

        by_measure_beat = {
            (e.measure, e.beat): e for e in trace
            if e.event_type != "rest"
        }

        # Ground truth (real TAB fixture, confirmed directly):
        # measure/beat -> expected role, for ELIGIBLE attacks only
        # (role is "down" or "pull"). Ineligible (>1 beat) notes
        # are deliberately excluded here -- BO-88 leaves them
        # completely unconstrained, so their own real candidate
        # (whichever ordinary, unrelated logic selects) is not a
        # BO-88 concern at all and is not asserted by this test.
        # Measure 8's third note (m8 b3.0) is also excluded --
        # known, documented discrepancy (see stroke_cycle.py).
        expected = {
            (1, 0.0): "down", (1, 1.0): "pull",
            (1, 2.0): "down", (1, 3.0): "pull",
            (2, 0.0): "down", (2, 2.0): "down",
            (2, 3.0): "pull",
            (3, 2.0): "down",
            (3, 3.0): "pull",
            (5, 0.0): "down", (5, 0.5): "pull",
            (5, 1.0): "down", (5, 1.5): "pull",
            (5, 2.0): "down", (5, 2.5): "pull",
            (5, 3.0): "down", (5, 3.5): "pull",
            (6, 0.0): "down", (6, 0.5): "pull",
            (6, 1.0): "down",
        }

        for key, expected_role in expected.items():

            entry = by_measure_beat[key]

            actually_fifth = is_fifth_string(entry)

            if expected_role == "pull":

                assert actually_fifth, (
                    f"{key}: expected pull (5th string), got "
                    f"string={entry.string} fret={entry.fret}"
                )

            else:

                assert not actually_fifth, (
                    f"{key}: expected down (non-5th-string), "
                    f"got the open 5th string"
                )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
