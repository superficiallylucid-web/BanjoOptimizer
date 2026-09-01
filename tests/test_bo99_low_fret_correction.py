"""
tests/test_bo99_low_fret_correction.py

Regression tests for BO-99: best_position()'s own string==1 bonus
reduced from +6 to +4 (BO-98's own direct A/B-confirmed smallest
safe correction), so that a genuine, much larger fret-band
difference (e.g. fret 5 vs fret 12) is no longer narrowly
outweighed by this string preference in the specific case where
no HP/phrase/chord evidence exists yet to arbitrate.

Real motivating case: the controlled Rhythmic Clawhammer Stroke
Cycle score's own "down"-role G4 notes, previously landing on the
impractical 3-12 (string 1, fret 12) purely via this narrow, 1-
point legacy-scoring margin, now correctly land on the practical
3-5 (string 3, fret 5) -- matching the score's own original target
TAB fixture.
"""

import sys

sys.path.insert(0, '.')

from fretboard import find_positions, best_position

from score_generator import generate_tab_from_template

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary


C_STANDARD = get_tunings()["C Standard"]

OPEN_G = get_tunings()["Open G"]

DOUBLE_C = get_tunings()["Double C"]

DOUBLE_D = get_tunings()["Double D"]


# ---------------------------------------------------------
# 1 -- direct unit confirmation of the exact scoring change
# ---------------------------------------------------------

def test_string_1_bonus_reduced_to_4():

    open_notes = C_STANDARD.notes[1:]

    positions = find_positions(67, open_notes)  # G4

    best_position(positions)

    fret12 = next(p for p in positions if p["fret"] == 12)

    fret5 = next(p for p in positions if p["fret"] == 5)

    # fret5/string3 = 5 (band) + 2 (string) = 7 (unchanged)
    assert fret5["score"] == 7

    # fret12/string1 = 2 (band) + 4 (string, reduced from 6) = 6
    assert fret12["score"] == 6

    # fret5 now genuinely wins.
    assert fret5["score"] > fret12["score"]


# ---------------------------------------------------------
# 2 -- real controlled score: 3-5 replaces 1-12
# ---------------------------------------------------------

def test_real_controlled_score_g4_now_selects_3_5():

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
            service, filename="test_bo99_rcsc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        # Every "down"-role G4 in the whole score now selects the
        # practical string 3/fret 5 -- confirmed real, none of
        # them land on string 1/fret 12 anywhere.
        down_role_entries = [
            e for e in trace
            if e.pitch == 67 and not (
                e.string == 4 and e.fret == 0
            ) and e.event_type != "rest"
        ]

        assert len(down_role_entries) > 10

        for entry in down_role_entries:

            assert entry.string == 3

            assert entry.fret == 5

        # No new high-position cascade: the whole score stays in
        # one low, practical HP throughout.
        assert all(
            e.hp_before is None or e.hp_before.low <= 8
            for e in trace if e.hp_before is not None
        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- BO-95's 5th-string/clawhammer behavior unaffected
# ---------------------------------------------------------

def test_real_controlled_score_fifth_string_unaffected():

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
            service, filename="test_bo99_rcsc_5th.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        # Real, confirmed: measure 1's own finger-thumb-finger-
        # thumb pattern (the primary BO-88 achievement) is intact
        # -- 5th string still lands exactly on the eligible "pull"
        # positions, unaffected by this fret-band/string-
        # preference change (a completely separate scoring
        # component).
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
# 4 -- Cmaj7/A4 (BO-74/83/95) remains unchanged
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
            service, filename="test_bo99_tcs_a4.mscz",
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
# 5 -- CSB G3/E4 (BO-95's own restoration) remains unchanged
# ---------------------------------------------------------

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
            service, filename="test_bo99_csb.mscz",
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
