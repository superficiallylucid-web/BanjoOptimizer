"""
tests/test_bo95_narrow_fifth_string_open_bonus.py

Regression tests for BO-95: narrows BO-93's own
following_working_fret_anchor requirement to the 5th string
specifically (position["string"] == FIFTH_STRING_INDEX), per
BO-94's own direct finding -- ordinary open strings (0-3) retain
their exact pre-BO-93 open_string_bonus behavior, regardless of
chord/following-anchor presence.

Real motivating cases:

- CSB, G3, measure 6: an ordinary open-string note on string 1 --
  BO-93 incorrectly required a following anchor for this too
  (CSB is chord-less, so this never existed, regressing G3 to a
  fretted realization). BO-95 restores it.

- CSB, E4, measure 6: cascaded from the G3 regression (G3's own
  shift changed the established HP, changing E4's own already-
  validated BO-62 result). Restoring G3 restores E4 as a direct
  consequence, not a separate fix.

- The controlled Rhythmic Clawhammer Stroke Cycle score's own
  long-note cases (always string 4 specifically) remain correctly
  excluded, since BO-93's own condition is preserved for the 5th
  string.
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

DOUBLE_D = get_tunings()["Double D"]


# ---------------------------------------------------------
# 1 -- controlled-score long notes remain correctly excluded
# from the 5th string (BO-93's own goal preserved)
# ---------------------------------------------------------

def test_real_controlled_score_long_notes_still_excluded():

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
            service, filename="test_bo95_rcsc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        def is_fifth_string(e):

            return e.string == 4 and e.fret == 0

        # The genuine long-note (role=None) onsets specifically --
        # not m3 b3.0, which is a real, eligible "pull" attack and
        # correctly IS the 5th string.
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
# 2 -- real CSB G3 regression restored
# ---------------------------------------------------------

def test_real_csb_g3_open_string_restored():

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
            service, filename="test_bo95_csb_g3.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        g3_entry = next(
            e for e in trace
            if e.measure == 6 and e.pitch == 55
        )

        # Real, confirmed: restored to the open realization
        # (string 1, fret 0) -- an ordinary open string, never the
        # 5th string, correctly unaffected by BO-93/95 either way.
        assert g3_entry.string == 1

        assert g3_entry.fret == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- real CSB E4 cascade restored (a direct consequence of
# restoring G3, not a separate fix)
# ---------------------------------------------------------

def test_real_csb_e4_cascade_restored():

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
            service, filename="test_bo95_csb_e4.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        e4_entries = [
            e for e in trace
            if e.measure == 6 and e.pitch == 64
        ]

        assert len(e4_entries) == 2

        # Real, confirmed: restored to BO-62's own original,
        # validated result (string 3, fret 2), not the regressed
        # BO-93 value (string 2, fret 4).
        for entry in e4_entries:

            assert entry.string == 3

            assert entry.fret == 2

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4 -- eligible 5th-string clawhammer notes remain intact
# ---------------------------------------------------------

def test_real_csb_g4_clawhammer_pattern_still_intact():

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
            service, filename="test_bo95_csb_g4.mscz",
            hp_trace_sink=trace
        )
    )

    try:

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


# ---------------------------------------------------------
# 5 -- Cmaj7/A4 (BO-74/83) remains unchanged
# ---------------------------------------------------------

def test_real_tcs_a4_cmaj7_unchanged():

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
            service, filename="test_bo95_tcs_a4.mscz",
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
# 6 -- ordinary open strings 0-3 unaffected by chord/following-
# anchor absence (exact pre-BO-93 behavior restored)
# ---------------------------------------------------------

def test_ordinary_open_strings_unaffected_by_missing_anchor():

    open_notes = DOUBLE_C.notes[1:] + [DOUBLE_C.notes[0]]

    # G3's own open candidate is on string 1, not the 5th string.
    # No following anchor at all -- must still receive the bonus,
    # exactly as before BO-93 existed.
    result = _choose_melody_position(
        55, open_notes,  # G3
        expected_attack_role=None
    )

    assert result["string"] == 1

    assert result["fret"] == 0
