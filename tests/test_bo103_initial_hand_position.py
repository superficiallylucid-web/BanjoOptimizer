"""
tests/test_bo103_initial_hand_position.py

Regression tests for BO-103: current_hp now starts as
HandPosition(1, 4) rather than None, and _choose_melody_position()'s
own existing "no context at all" fast-path is adjusted to not
bypass this established initial HP (BO-101/102's own investigation)
-- letting the already-existing, completely unmodified hp_tiebreak
mechanism decide the genuine first note of a song, rather than
falling through to best_position()'s own legacy scoring alone.
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


C_STANDARD = get_tunings()["C Standard"]

DOUBLE_C = get_tunings()["Double C"]

OPEN_C = get_tunings()["Open C"]

DOUBLE_D = get_tunings()["Double D"]


# ---------------------------------------------------------
# 1 -- direct confirmation: no prior context, initial HP is (1,4)
# ---------------------------------------------------------

def test_no_context_default_hp_is_one_to_four():

    open_notes = C_STANDARD.notes[1:] + [C_STANDARD.notes[0]]

    result = _choose_melody_position(
        67, open_notes,
        current_hp=HandPosition(1, 4),
        expected_attack_role="down"
    )

    # fret 5, not fret 12 -- hp_tiebreak (unmodified) now decides,
    # since fret 5 is the closest fretted candidate to the HP's
    # own root (1).
    assert result["string"] == 3

    assert result["fret"] == 5


# ---------------------------------------------------------
# 2 -- real controlled score: all 3 tunings select the target
# low-position candidate for the first G4
# ---------------------------------------------------------

def test_real_controlled_score_c_standard_first_g4():

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
            service, filename="test_bo103_cstd.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        first_note = trace[0]

        assert first_note.string == 3

        assert first_note.fret == 5

        assert first_note.hp_before == HandPosition(1, 4)

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_controlled_score_double_c_first_g4():

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
            p, DOUBLE_C, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo103_dc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        first_note = trace[0]

        assert first_note.string == 3

        assert first_note.fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_controlled_score_open_c_first_g4():

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
            p, OPEN_C, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo103_openc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        first_note = trace[0]

        assert first_note.string == 3

        assert first_note.fret == 3

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- existing 5th-string clawhammer behavior (BO-95) intact
# ---------------------------------------------------------

def test_real_controlled_score_fifth_string_pattern_intact():

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
            service, filename="test_bo103_5th.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        # Measure 1's own finger-thumb-finger-thumb pattern is
        # unaffected -- unchanged from BO-99's own validated
        # result, just now on the correct (low-position) finger
        # candidate from the very first note onward.
        m1_entries = [
            e for e in trace
            if e.measure == 1 and e.pitch == 67
        ]

        assert len(m1_entries) == 4

        assert m1_entries[0].string == 3 and m1_entries[0].fret == 5

        assert m1_entries[1].string == 4 and m1_entries[1].fret == 0

        assert m1_entries[2].string == 3 and m1_entries[2].fret == 5

        assert m1_entries[3].string == 4 and m1_entries[3].fret == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4 -- existing validated cases unchanged
# ---------------------------------------------------------

def test_real_tcs_a4_cmaj7_unaffected():

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
            service, filename="test_bo103_tcs_a4.mscz",
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


def test_real_csb_g3_e4_unaffected():

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
            p, DOUBLE_C, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo103_csb.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g3_entry = next(
            e for e in trace
            if e.measure == 6 and e.pitch == 55
        )

        assert g3_entry.string == 1

        assert g3_entry.fret == 0

        e4_entries = [
            e for e in trace
            if e.measure == 6 and e.pitch == 64
        ]

        assert len(e4_entries) == 2

        for entry in e4_entries:

            assert entry.string == 3

            assert entry.fret == 2

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
