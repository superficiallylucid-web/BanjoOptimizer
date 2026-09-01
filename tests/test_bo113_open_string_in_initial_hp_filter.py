"""
tests/test_bo113_open_string_in_initial_hp_filter.py

Regression tests for BO-113: BO-111's own initial-HP candidate
filter now retains open-string candidates (fret == 0) regardless
of the initial HandPosition(1, 4)'s own numeric range, rather than
excluding them by a plain fret-vs-range comparison.

Real motivating case (BO-112's own direct investigation): CSB/Open
C's own real E4 has fret0(str3) and fret4(str2) exactly tied on raw
score. The prior, un-fixed filter (`current_hp.low <= fret`, i.e.
`1 <= fret`) silently discarded fret0 before the sort key was even
reached, since 0 < 1 -- not a phrase-coverage or HP-continuity
decision at all, a plain filtering defect.
"""

import sys

sys.path.insert(0, '.')

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


OPEN_C = get_tunings()["Open C"]

C_STANDARD = get_tunings()["C Standard"]

DOUBLE_C = get_tunings()["Double C"]

OPEN_G = get_tunings()["Open G"]


def _first_match(trace, measure, beat, pitch):

    return next(
        e for e in trace
        if e.measure == measure and e.beat == beat
        and e.pitch == pitch
    )


# ---------------------------------------------------------
# 1 -- primary target: CSB Open C E4 now selects 1-0
# ---------------------------------------------------------

def test_real_csb_open_c_e4_selects_1_0():

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
            p, OPEN_C, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo113_csb_openc_e4.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 1, 3.0, 64)

        assert entry.string == 3

        assert entry.fret == 0

        assert entry.event_type == "open_note"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 2 -- CSB C Standard / Double C remain unchanged
# ---------------------------------------------------------

def test_real_csb_c_standard_g4_unchanged():

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
            service, filename="test_bo113_csb_cstd.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 7, 0.0, 67)

        assert entry.string == 3

        assert entry.fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_csb_double_c_g4_unchanged():

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
            service, filename="test_bo113_csb_dc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 7, 0.0, 67)

        assert entry.string == 3

        assert entry.fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- Rhythmic Clawhammer Stroke Cycle, all 3 tunings unchanged
# ---------------------------------------------------------

def test_real_controlled_score_c_standard_unchanged():

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
            service, filename="test_bo113_rcsc_cstd.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 1, 0.0, 67)

        assert entry.string == 3

        assert entry.fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_controlled_score_double_c_unchanged():

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
            service, filename="test_bo113_rcsc_dc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 1, 0.0, 67)

        assert entry.string == 3

        assert entry.fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_controlled_score_open_c_unchanged():

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
            service, filename="test_bo113_rcsc_openc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 1, 0.0, 67)

        assert entry.string == 3

        assert entry.fret == 3

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4 -- BO-95 fifth-string clawhammer behavior unchanged
# ---------------------------------------------------------

def test_real_controlled_score_fifth_string_pattern_unchanged():

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
            service, filename="test_bo113_5th.mscz",
            hp_trace_sink=trace
        )
    )

    try:

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
# 5 -- earned-HP case confirms this special treatment applies
# only to the unearned initial-HP filter
# ---------------------------------------------------------

def test_real_white_christmas_earned_hp_unaffected():

    import os

    p = MuseScoreFile("scores/White Christmas.mscz")

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, OPEN_G, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename="test_bo113_wc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        for measure in (19, 20):

            entry = _first_match(trace, measure, 0.0, 67)

            assert entry.string == 2

            assert entry.fret == 8

            # A genuinely earned HP, not the initial (1, 4) --
            # confirms this BO's own filter never applies here.
            assert entry.hp_before == entry.hp_after

            assert entry.hp_before.low != 1 or entry.hp_before.high != 4

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
