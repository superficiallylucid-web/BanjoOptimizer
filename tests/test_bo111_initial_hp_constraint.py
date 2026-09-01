"""
tests/test_bo111_initial_hp_constraint.py

Regression tests for BO-111: for the genuine, unearned initial HP
(1, 4) from BO-103, membership in that HP is now treated as an
authoritative constraint -- mirroring the existing chord-onset
early-return pattern -- so candidates inside it are preferred
before phrase_notes_played (which has no awareness of HP at all,
per BO-109's own investigation) can move the hand elsewhere.

This is a candidate-availability FILTER (matching BO-88's own
rhythmic-filter architecture), not a direct-return shortcut: the
full, existing sort key (including phrase_notes_played) still
decides among whatever survives inside the initial HP -- confirmed
essential during implementation, since an early, incorrect version
that called best_position() directly bypassed phrase coverage
entirely and reintroduced a legacy string-preference regression
(CSB/Double C's own E4).

hp_is_earned becomes True only once current_hp genuinely differs
from (1, 4) for the first time -- not merely "any note has been
decided" (confirmed real: the primary CSB/Open C target case is
measure 7, many notes in, with every preceding note legitimately
staying inside (1, 4) the whole time).
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

DOUBLE_D = get_tunings()["Double D"]

OPEN_G = get_tunings()["Open G"]


def _first_match(trace, measure, beat, pitch):

    return next(
        e for e in trace
        if e.measure == measure and e.beat == beat
        and e.pitch == pitch
    )


# ---------------------------------------------------------
# 1 -- primary target: CSB Open C G4 now selects 1-3
# ---------------------------------------------------------

def test_real_csb_open_c_g4_selects_1_3():

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
            service, filename="test_bo111_csb_openc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 7, 0.0, 67)

        assert entry.string == 3

        assert entry.fret == 3

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 2-3 -- CSB C Standard / Double C remain correct
# ---------------------------------------------------------

def test_real_csb_c_standard_unaffected():

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
            service, filename="test_bo111_csb_cstd.mscz",
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


def test_real_csb_double_c_unaffected():

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
            service, filename="test_bo111_csb_dc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g4_entry = _first_match(trace, 7, 0.0, 67)

        assert g4_entry.string == 3

        assert g4_entry.fret == 5

        # The E4/G3 cascade (BO-95/99) remains fully protected --
        # confirmed essential during implementation.
        e4_entries = [
            e for e in trace
            if e.measure == 6 and e.pitch == 64
        ]

        for entry in e4_entries:

            assert entry.string == 3

            assert entry.fret == 2

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4-6 -- Rhythmic Clawhammer Stroke Cycle, all 3 tunings
# ---------------------------------------------------------

def test_real_controlled_score_c_standard():

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
            service, filename="test_bo111_rcsc_cstd.mscz",
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


def test_real_controlled_score_double_c():

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
            service, filename="test_bo111_rcsc_dc.mscz",
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


def test_real_controlled_score_open_c():

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
            service, filename="test_bo111_rcsc_openc.mscz",
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
# 7 -- a later, genuinely earned HP still permits phrase
# coverage to outrank HP exactly as before BO-111
# ---------------------------------------------------------

def test_real_white_christmas_earned_hp_phrase_coverage_unaffected():

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
            service, filename="test_bo111_wc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        for measure in (19, 20):

            entry = _first_match(trace, measure, 0.0, 67)

            assert entry.string == 2

            assert entry.fret == 8

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


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
            service, filename="test_bo111_a4.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 2, 1.5, 69)

        assert entry.string == 2

        assert entry.fret == 7

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
