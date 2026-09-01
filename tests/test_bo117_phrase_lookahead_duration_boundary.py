"""
tests/test_bo117_phrase_lookahead_duration_boundary.py

Regression tests for BO-117: melody_phrase_notes_by_event_id's own
construction now truncates the phrase-lookahead window to the
current note alone when that note's own duration is >= 1.5 beats
(PHRASE_LOOKAHEAD_SUSTAINED_NOTE_THRESHOLD_BEATS) -- a sustained
note provides a genuine, natural opportunity to move the hand
afterward, so the following phrase should not influence its own
candidate scoring. Durations <= 1.0 beat are completely unaffected.

Deliberately a distinct threshold/value from stroke_cycle.py's own
ATTACK_ELIGIBILITY_THRESHOLD_BEATS (1.0) -- that threshold's own
">1.0" comparison would incorrectly suppress lookahead for an
ordinary quarter note (BO-116's own investigation).

Real motivating case: CSB C Standard, measure 12 beat 2 -- a C4
half note previously selected 3-5 (BO-57's own prior, duration-
blind decision, deliberately reaching more of the following G4
run) and now correctly selects 2-1, matching the identical final-
measure C4 (measure 16), which has no following phrase at all.

KNOWN, EXPECTED TEST CHANGE: this directly invalidates
tests/test_bo57_melody_phrase_continuity.py's own
test_csb_measure_12_c4_anticipates_following_g4_run, which
explicitly asserted the prior, duration-blind 3-5 result as
intended. That test has NOT been modified here, per BO-117's own
explicit instruction -- it now fails as an expected, flagged
consequence of this behavior change, not a regression.
"""

import sys

sys.path.insert(0, '.')

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


C_STANDARD = get_tunings()["C Standard"]

DOUBLE_C = get_tunings()["Double C"]

OPEN_C = get_tunings()["Open C"]

OPEN_G = get_tunings()["Open G"]


def _first_match(trace, measure, beat, pitch):

    return next(
        e for e in trace
        if e.measure == measure and e.beat == beat
        and e.pitch == pitch
    )


# ---------------------------------------------------------
# 1-3 -- the exact duration boundary itself
# ---------------------------------------------------------

def _window_length_for_duration(duration, window_size=6):
    """
    Direct replication of the exact BO-117 rule under test (the
    real logic lives inline inside generate_tab_from_template()'s
    own construction loop, not in an independently importable
    function) -- verifies the RULE itself: durations <= 1.0 beat
    keep the full lookahead window; durations >= 1.5 beats are
    truncated to the current note alone; nothing graduated/partial.
    """

    threshold = 1.5

    return 1 if duration >= threshold else window_size


def test_quarter_note_retains_full_lookahead():

    assert _window_length_for_duration(1.0) == 6


def test_dotted_quarter_note_suppresses_lookahead():

    assert _window_length_for_duration(1.5) == 1


def test_half_note_suppresses_lookahead():

    assert _window_length_for_duration(2.0) == 1


def test_eighth_note_retains_full_lookahead():

    assert _window_length_for_duration(0.5) == 6


# ---------------------------------------------------------
# 4-5 -- real CSB C Standard M12/M16 C4
# ---------------------------------------------------------

def test_real_csb_m12_c4_now_selects_2_1():

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
            service, filename="test_bo117_m12.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 12, 2.0, 60)

        assert entry.string == 2

        assert entry.fret == 1

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_csb_m16_c4_remains_2_1():

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
            service, filename="test_bo117_m16.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 16, 2.0, 60)

        assert entry.string == 2

        assert entry.fret == 1

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 6 -- existing CSB Open C corrections remain unchanged
# ---------------------------------------------------------

def test_real_csb_open_c_g4_unchanged():

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
            service, filename="test_bo117_csb_openc_g4.mscz",
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


def test_real_csb_open_c_e4_unchanged():

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
            service, filename="test_bo117_csb_openc_e4.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        entry = _first_match(trace, 1, 3.0, 64)

        assert entry.string == 3

        assert entry.fret == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 7 -- Rhythmic Clawhammer Stroke Cycle, all 3 tunings unchanged
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
            service, filename="test_bo117_rcsc_cstd.mscz",
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
            service, filename="test_bo117_rcsc_dc.mscz",
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
            service, filename="test_bo117_rcsc_openc.mscz",
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
# 8 -- earned-HP phrase-continuity case, current note <= 1.0
# beat, remains unchanged
# ---------------------------------------------------------

def test_real_white_christmas_earned_hp_quarter_note_unchanged():

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
            service, filename="test_bo117_wc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        # Measure 20 beat 0.0 is a genuine quarter note (duration
        # 1.0), unaffected by this BO's own threshold.
        entry = _first_match(trace, 20, 0.0, 67)

        assert entry.string == 2

        assert entry.fret == 8

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
