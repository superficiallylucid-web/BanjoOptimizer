"""
tests/test_bo62_within_hp_offset.py

Regression tests for BO-62: an HP-root/fret-offset tiebreak
(NOT a literal finger assignment -- no such assignment exists
elsewhere in this codebase) that decides between multiple melody
candidates that are BOTH inside the current HP AND tied on
phrase coverage -- a gap BO-60's own hp_tiebreak structurally
cannot resolve, since it only ever separates inside from outside.

Positioned after phrase_notes_played and BO-60's hp_tiebreak,
before the legacy tiebreaks -- active only in the same chord-less
scope (no_chord_anchor_at_all) BO-60's own mechanism already
requires.
"""

import sys

sys.path.insert(0, '.')

from score_generator import _choose_melody_position

from tunings import get_tunings

from hand_position import HandPosition

from models import BoxMelodyNote

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


C_STANDARD = get_tunings()["C Standard"]

DOUBLE_C = get_tunings()["Double C"]

DOUBLE_D = get_tunings()["Double D"]


def _generate_with_trace(path, tuning, filename):

    p = MuseScoreFile(path)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    trace = []

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            "templates/TAB_linked_Treble_Example.mscz", "output",
            service, filename=filename, hp_trace_sink=trace
        )
    )

    return output_path, trace


# ---------------------------------------------------------
# 1 -- direct unit test: BO-62 tiebreak itself
# ---------------------------------------------------------

def test_within_hp_offset_prefers_candidate_closest_to_root():

    open_notes = DOUBLE_C.notes[1:]

    # current HP (2,5); E4's own real candidates fret 4 (offset
    # 2 from root) and fret 2 (offset 0) both remain inside it,
    # with no phrase window at all -- a clean, guaranteed
    # universal phrase tie (see test_bo60's own established
    # pattern for why this is the reliable way to isolate a
    # tiebreak, rather than a short window that could
    # accidentally interact with BO-58's own quality filtering).
    result = _choose_melody_position(
        64, open_notes, current_hp=HandPosition(2, 5),
        previous_position={"string": 2, "fret": 2, "score": 0}
    )

    # fret 2 is NOT E4's own best-scored candidate in this tuning
    # (fret 4 scores 12, fret 2 scores 10) -- it wins purely for
    # being closer to the HP root, directly proving the tiebreak.
    assert result["fret"] == 2

    assert result["string"] == 3


# ---------------------------------------------------------
# 2 -- phrase coverage still outranks BO-62 even when both
# candidates are inside the same HP
# ---------------------------------------------------------

def test_genuine_phrase_difference_beats_within_hp_offset():

    open_notes = DOUBLE_C.notes[1:]

    # A directly-constructed synthetic phrase note, reachable
    # from fret 4 (positions_covering_fret includes 3,4) but NOT
    # from fret 2 -- gives fret 4 (offset 2, the "worse" BO-62
    # candidate) a genuine, real phrase-coverage advantage over
    # fret 2 (offset 0), despite fret 2 being closer to the root.
    synthetic_note = BoxMelodyNote(
        midi=0, measure=0, beat=0.0, realizations=[],
        has_open_realization=False,
        fretted_positions={3, 4}
    )

    result = _choose_melody_position(
        64, open_notes, melody_phrase_notes=[synthetic_note],
        current_hp=HandPosition(2, 5),
        previous_position={"string": 2, "fret": 2, "score": 0}
    )

    # fret 4 must win -- phrase_notes_played sits earlier in the
    # sort key than within_hp_offset, so a real phrase difference
    # is never overridden by the root-distance preference.
    assert result["fret"] == 4

    assert result["string"] == 2


# ---------------------------------------------------------
# 3 -- HP membership (BO-60) still outranks BO-62
# ---------------------------------------------------------

def test_hp_membership_still_outranks_within_hp_offset():

    open_notes = DOUBLE_C.notes[1:]

    # current_hp (9,12): only E4's own fret-9 candidate is
    # inside it (offset 0); fret 4 and fret 2 are both outside,
    # despite fret 4 having a materially BETTER intrinsic score
    # (12) than fret 9 (8). The single inside candidate must
    # still win -- BO-60's own inside-vs-outside decision is
    # never reachable/overridable by BO-62 at all.
    result = _choose_melody_position(
        64, open_notes, current_hp=HandPosition(9, 12),
        previous_position={"string": 1, "fret": 9, "score": 0}
    )

    assert result["fret"] == 9

    assert result["string"] == 1


# ---------------------------------------------------------
# 4 -- chord-anchored melody: BO-62 must be completely inert
# ---------------------------------------------------------

def test_chord_anchored_melody_bo62_inert():

    open_notes = DOUBLE_D.notes[1:]

    # Real Christmas Song / Cmaj7 A4 case: chord anchor present.
    # A4's own real candidates include fret 12 (inside current_
    # hp=(9,12), offset 3 from root) and fret 7 (outside it,
    # movement 2 via BO-60's own between-HP metric). If BO-62
    # were NOT gated off for chord-anchored melody, fret 12 would
    # win (offset 3 is still "inside", and hp_tiebreak alone
    # can't distinguish it from any other inside candidate --
    # there being only one here means it would trivially win).
    # The real, correct, already-validated answer is fret 7,
    # confirming BO-62 is genuinely inert here.
    result = _choose_melody_position(
        69, open_notes,
        working_fret_anchor=9,
        current_hp=HandPosition(9, 12)
    )

    assert result["fret"] == 7

    assert result["string"] == 2


# ---------------------------------------------------------
# 5 -- real CSB/gCGCD E4 regression (measures 6, 10, 14)
# ---------------------------------------------------------

def test_real_csb_gCGCD_e4_regression():

    import os

    output_path, trace = _generate_with_trace(
        "scores/Cousin Sally Brown.mscz", DOUBLE_C,
        "test_bo62_e4_regression.mscz"
    )

    try:

        e4_entries = [
            e for e in trace
            if e.pitch == 64 and e.event_type == "fretted_note"
        ]

        # Real, confirmed: every single E4 occurrence in this
        # piece -- including measures 6, 10, and 14, previously
        # generated at fret 4 -- now lands at fret 2, matching
        # every other E4 occurrence in the piece.
        for entry in e4_entries:

            assert entry.fret == 2, (
                f"m{entry.measure} E4 expected fret 2, got "
                f"fret {entry.fret}"
            )

            assert entry.string == 3

        assert len(e4_entries) > 10

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 6 -- real CSB/gCGCD G4 regression (BO-60's own fix, protected)
# ---------------------------------------------------------

def test_real_csb_gCGCD_g4_still_protected():

    import os

    output_path, trace = _generate_with_trace(
        "scores/Cousin Sally Brown.mscz", DOUBLE_C,
        "test_bo62_g4_protected.mscz"
    )

    try:

        g4_entries = [
            e for e in trace
            if e.pitch == 67 and e.event_type == "fretted_note"
        ]

        for entry in g4_entries:

            assert entry.fret == 5

            assert entry.string == 3

        assert len(g4_entries) == 15  # 3 per each of 5 repeats

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 7 -- real chord-anchored regression (TCS Cmaj7/A4), protected
# ---------------------------------------------------------

def test_real_tcs_a4_chord_anchored_regression():

    import os

    output_path, trace = _generate_with_trace(
        "scores/The Christmas Song.mscz", DOUBLE_D,
        "test_bo62_a4_protected.mscz"
    )

    try:

        a4_entry = next(
            e for e in trace
            if e.measure == 2 and e.pitch == 69
        )

        assert a4_entry.fret == 7

        assert a4_entry.string == 2

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
