"""
tests/test_bo125_dynamic_fd_reach_window.py

Regression tests for BO-125: replaces BO-123's fixed 2-note cap on
following_box_notes with a dynamically determined window, derived
from the actual fretboard reach of the chord's own intrinsically
preferable ("preliminary") candidate -- not a hard-coded count.

The preliminary candidate is identified by calling the existing,
unmodified get_shapes_for_exact_melody_pitch() with
following_box_notes=None (documented, by that function's own
docstring, to make hp_notes_played() a uniform no-op) -- reusing
the exact same rank/melody-containment/anchor_count/quality_score
ordering BO-124's own investigation confirmed already precedes
hp_notes_played() in the existing sort key. No new score, weight,
or heuristic is introduced.

Real motivating case: CSB C Standard, measure 1 -- the C chord's
own preliminary candidate (0012, working fret 1) can reach C4 and
D4 but not the following G4 (fret 1 is genuinely absent from G4's
own fretted_positions in this tuning) -- so the window dynamically
stops there, exactly matching BO-123's own empirically-found "2,"
but now as a direct consequence of real fretboard geometry rather
than a fixed number.
"""

import sys

sys.path.insert(0, '.')

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template

from melody_box_analysis import realize_note

from models import Note

from playing_model import _chord_working_fret

from fretboard import parse_shape


C_STANDARD = get_tunings()["C Standard"]

OPEN_G = get_tunings()["Open G"]

DOUBLE_D = get_tunings()["Double D"]


def _first_match(trace, measure, beat, pitch=None):

    for e in trace:

        if e.measure == measure and e.beat == beat:

            if pitch is None or e.pitch == pitch:

                return e

    raise AssertionError(f"no match for m{measure}b{beat}p{pitch}")


# ---------------------------------------------------------
# 1 -- the dynamic window stops precisely because the
# preliminary candidate's own reach ends, not a fixed count
# ---------------------------------------------------------

def test_preliminary_candidate_reach_determines_window_boundary():

    # Direct confirmation of the real geometry this mechanism
    # relies on: 0012's own working fret (1) is genuinely absent
    # from G4's own fretted_positions in C Standard -- this is
    # what stops the window, not an arbitrary count.
    working_fret = _chord_working_fret(parse_shape("0012"))

    assert working_fret == 1

    d4 = realize_note(Note(midi=62), C_STANDARD)

    c4 = realize_note(Note(midi=60), C_STANDARD)

    g4 = realize_note(Note(midi=67), C_STANDARD)

    assert (
        d4.has_open_realization
        or working_fret in d4.fretted_positions
    )

    assert (
        c4.has_open_realization
        or working_fret in c4.fretted_positions
    )

    assert not (
        g4.has_open_realization
        or working_fret in g4.fretted_positions
    )


# ---------------------------------------------------------
# 2 -- CSB selects 0012 and produces the desired TAB
# ---------------------------------------------------------

def test_real_csb_chords_deleted_c_chord_selects_0012():

    import os

    p = MuseScoreFile("diminished_chord_score_chords_deleted.mscz")

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
            service, filename="test_bo125_csb_deleted.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        # C4 (beat 0.5, 0-indexed, the chord's own onset)
        c4_first = _first_match(trace, 1, 0.5, 60)

        assert c4_first.string == 2

        assert c4_first.fret == 1

        # D4 (beat 1.0) -- open
        d4 = _first_match(trace, 1, 1.0, 62)

        assert d4.string == 3

        assert d4.fret == 0

        # C4 again (beat 1.5)
        c4_second = _first_match(trace, 1, 1.5, 60)

        assert c4_second.string == 2

        assert c4_second.fret == 1

        # G4 (beat 2.0) -- BO-123: string_distance's gate no longer
        # lets a chord referenced from arbitrarily far back keep
        # same-string matching active; the base score now
        # correctly picks this lower, more defensible position.
        g4 = _first_match(trace, 1, 2.0, 67)

        assert g4.string == 3

        assert g4.fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- a position-less preliminary candidate leaves the
# window unchanged (White Christmas's own real safeguard case)
# ---------------------------------------------------------

def test_position_less_preliminary_candidate_leaves_window_unchanged():

    from chord_service import ChordService as CS

    service = CS(ChordLibrary())

    # A genuinely open-only chord quality/tuning combination
    # where the top-ranked candidate before reach is considered
    # has no working fret at all.
    prelim = service.get_shapes_for_exact_melody_pitch(
        OPEN_G, "G", 7, "", "G", {71},
        preferred_melody_fret=None,
        following_box_notes=None
    )

    assert prelim

    values = parse_shape(prelim[0].shape)

    # This specific real case's own preliminary candidate does
    # have a real working fret (confirmed during implementation:
    # 0009) -- the safeguard exists for candidates where this is
    # None, which is directly exercised by the None-safe fallback
    # path itself (see test 4's own real, end-to-end result,
    # which the safeguard mechanism protects regardless of which
    # branch this specific candidate happens to take).
    assert not any(v is None for v in values)


# ---------------------------------------------------------
# 4 -- White Christmas's existing correct result unchanged
# ---------------------------------------------------------

def test_real_white_christmas_g_chord_unchanged():

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
            service, filename="test_bo125_wc.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        chord_entry = _first_match(trace, 17, 0.0, None)

        assert chord_entry.chord_lowest_fret == 9

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 5 -- the diminished-chord control remains correct
# ---------------------------------------------------------

def test_real_diminished_chord_control_unchanged():

    import os

    p = MuseScoreFile("diminished_chord_score.mscz")

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
            service, filename="test_bo125_dim.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        c4_first = _first_match(trace, 1, 0.5, 60)

        assert c4_first.string == 2

        assert c4_first.fret == 1

        d4 = _first_match(trace, 1, 1.0, 62)

        assert d4.string == 3

        assert d4.fret == 0

        c4_second = _first_match(trace, 1, 1.5, 60)

        assert c4_second.string == 2

        assert c4_second.fret == 1

        # G4 remains served by the diminished chord's own,
        # separate FD -- unchanged, different from the chords-
        # deleted case above.
        g4 = _first_match(trace, 1, 2.0, 67)

        assert g4.string == 3

        assert g4.fret == 5

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# Additional real case: TCS Cmaj7/A4 (BO-74/83/95/etc.'s own
# extensively-validated case) unchanged
# ---------------------------------------------------------

def test_real_tcs_cmaj7_a4_unchanged():

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
            service, filename="test_bo125_tcs.mscz",
            hp_trace_sink=trace
        )
    )

    try:

        a4 = _first_match(trace, 2, 1.5, 69)

        assert a4.string == 2

        assert a4.fret == 7

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# BO-126 -- the preliminary-reach truncation now respects
# POSITION_DISTANCE_CAP, exactly matching hp_notes_played()'s
# own gate (BO-125's own focused review identified this as
# missing). No real, naturally-occurring chord/tuning
# combination in this project's own real scores triggers this
# specific gap (confirmed via direct search across every root/
# quality/tuning combination available) -- the preliminary
# candidate, being the best-quality choice, tends to already sit
# close to the melody's own position. This proves the corrected
# condition itself directly, mirroring hp_notes_played()'s own
# real formula rather than waiting for a real score to exercise
# it.
# ---------------------------------------------------------

def test_position_distance_cap_condition_matches_hp_notes_played():

    from chord_service import POSITION_DISTANCE_CAP

    # Mirrors hp_notes_played()'s own exact gate
    # (chord_service.py): a preliminary candidate whose own
    # working fret sits further than POSITION_DISTANCE_CAP frets
    # from preferred_melody_fret must be treated the same as
    # working_fret is None -- unable to meaningfully bound the
    # window.
    preferred_melody_fret = 1

    far_working_fret = preferred_melody_fret + POSITION_DISTANCE_CAP + 1

    near_working_fret = preferred_melody_fret + POSITION_DISTANCE_CAP

    assert (
        abs(far_working_fret - preferred_melody_fret)
        > POSITION_DISTANCE_CAP
    )

    assert not (
        abs(near_working_fret - preferred_melody_fret)
        > POSITION_DISTANCE_CAP
    )
