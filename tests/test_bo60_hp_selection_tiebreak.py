"""
tests/test_bo60_hp_selection_tiebreak.py

Regression tests for BO-60: the persistent HP tiebreak in
_choose_melody_position(), positioned immediately after BO-57/58
phrase coverage (so it can never override a genuine phrase-
coverage difference) and gated to the same chord-less situation
phrase coverage itself is scoped to (so it never interferes with
the existing chord-anchor/fret_distance machinery).
"""

import sys

sys.path.insert(0, '.')

from score_generator import _choose_melody_position

from tunings import get_tunings

from melody_box_analysis import realize_note

from hand_position import HandPosition

from models import Note


C_STANDARD = get_tunings()["C Standard"]

DOUBLE_C = get_tunings()["Double C"]

OPEN_NOTES_C_STANDARD = C_STANDARD.notes[1:]

OPEN_NOTES_DOUBLE_C = DOUBLE_C.notes[1:]


# ---------------------------------------------------------
# 1 -- real CSB/gCGCD G4 case: exact phrase tie, HP decides
# ---------------------------------------------------------

def test_real_csb_gCGCD_g4_phrase_tie_hp_decides():

    open_notes = OPEN_NOTES_DOUBLE_C

    # Real chain leading to the first G4 (measure 7): confirmed
    # real sequence establishing HP (2,5) at A3, never genuinely
    # left before the G4 (E4 at fret 4, measure 6, stays inside).
    a3 = _choose_melody_position(57, open_notes)

    assert a3["fret"] == 2

    current_hp = HandPosition(2, 5)

    window = [
        Note(midi=67), Note(midi=67), Note(midi=67),
        Note(midi=64), Note(midi=62), Note(midi=60)
    ]

    realized_window = [
        realize_note(n, DOUBLE_C, quality_filtered=True)
        for n in window
    ]

    # previous_position must reflect the real immediately-
    # preceding note (E4 at fret 4) -- omitting it entirely
    # triggers an unrelated, existing "no context at all" fast
    # path that bypasses the sort key (and therefore this whole
    # tiebreak) altogether, which is never the real situation
    # for a note this deep into an actual song.
    g4 = _choose_melody_position(
        67, open_notes, melody_phrase_notes=realized_window,
        current_hp=current_hp,
        previous_position={"string": 2, "fret": 4, "score": 12}
    )

    # Real, confirmed: fret 5 and fret 7 genuinely tie at
    # phrase_notes_played=3 each -- with no real phrase winner,
    # the HP tiebreak correctly prefers fret 5 (inside (2,5))
    # over fret 7 (outside it, despite its own higher intrinsic
    # best_position() score).
    assert g4["fret"] == 5

    assert g4["string"] == 3


# ---------------------------------------------------------
# 2 -- real CSB/gCGBD C4 case: genuine phrase-coverage
# difference beats HP entirely -- this is the essential test
# proving BO-60 is not "inside HP always wins"
# ---------------------------------------------------------

def test_real_csb_gCGBD_c4_phrase_difference_beats_hp():

    open_notes = OPEN_NOTES_C_STANDARD

    # Real chain: G3(open) -> A3@2, establishing HP (2,5).
    a3 = _choose_melody_position(57, open_notes)

    assert a3["fret"] == 2

    current_hp = HandPosition(2, 5)

    window = [
        Note(midi=60), Note(midi=64), Note(midi=62),
        Note(midi=60), Note(midi=57), Note(midi=55)
    ]

    realized_window = [
        realize_note(n, C_STANDARD, quality_filtered=True)
        for n in window
    ]

    c4 = _choose_melody_position(
        60, open_notes, melody_phrase_notes=realized_window,
        current_hp=current_hp
    )

    # Real, confirmed: fret 1 achieves phrase_notes_played=6
    # (every following note stays playable); fret 5 (inside the
    # current HP) only achieves 4. This is a genuine, decisive
    # phrase-coverage difference -- BO-60's HP tiebreak must
    # never even be reached here, let alone override it.
    assert c4["fret"] == 1

    assert c4["string"] == 2


# ---------------------------------------------------------
# 3 -- real Christmas Song A4 case: chord-anchored, HP tiebreak
# must not activate at all -- existing fret_distance decides
# ---------------------------------------------------------

def test_real_tcs_a4_chord_anchored_hp_tiebreak_inactive():

    double_d = get_tunings()["Double D"]

    open_notes = double_d.notes[1:]

    # Real: Cmaj7 chord establishes HP (9,12); A4 has a chord
    # anchor (working_fret_anchor) from that same chord.
    a4 = _choose_melody_position(
        69, open_notes,
        working_fret_anchor=9,
        current_hp=HandPosition(9, 12)
    )

    # Real, confirmed correct (pre-BO-60, and preserved): fret 7
    # wins via the existing chord-anchor/fret_distance machinery
    # -- NOT fret 12, even though fret 12 is inside current_hp.
    # The HP tiebreak must be fully inactive here.
    assert a4["fret"] == 7

    assert a4["string"] == 2


# ---------------------------------------------------------
# 4 -- direct synthetic unit test: inside-HP candidate wins on
# an exact phrase tie
# ---------------------------------------------------------

def test_synthetic_inside_hp_wins_on_exact_phrase_tie():

    open_notes = C_STANDARD.notes[1:]

    # HP (8,11): among E4's own real candidates (fret 16, 9, 5,
    # 2), fret 9 is the ONLY one inside this specific window --
    # avoids a real ambiguity discovered while building this test
    # (a wider HP like (2,5) contains BOTH fret 5 and fret 2,
    # which would then be decided by string_distance rather than
    # by hp_tiebreak itself, not genuinely isolating what this
    # test claims to prove).
    current_hp = HandPosition(8, 11)

    # No melody_phrase_notes at all (not merely a short window):
    # _melody_phrase_notes_played() returns 0 unconditionally
    # when its own window is empty/None, for every candidate --
    # a clean, guaranteed universal tie on phrase coverage that
    # cannot vary by which candidates BO-58's own quality
    # filtering happens to consider "good" for this pitch,
    # letting hp_tiebreak be the genuine, sole differentiator.
    #
    # previous_position is synthetic (any non-None value) --
    # required only to avoid an unrelated, existing "no context
    # at all" fast path that bypasses the sort key entirely when
    # previous_position is None (confirmed real: this function
    # returns best_position()'s own result directly in that
    # case, skipping every tiebreak including this one -- never
    # the real situation for a note this deep into an actual
    # song, so never a genuine test of the mechanism either).
    result = _choose_melody_position(
        64, open_notes, current_hp=current_hp,
        previous_position={"string": 0, "fret": 8, "score": 0}
    )

    # fret 9 is NOT E4's own best-scored candidate overall (fret
    # 2 scores higher) -- it wins here purely because it is the
    # only one inside current_hp, directly proving the tiebreak
    # itself, not a coincidence of intrinsic scoring.
    assert result["fret"] == 9


# ---------------------------------------------------------
# 5 -- direct synthetic unit test: minimum HP-root movement
# wins when no candidate is inside the current HP
# ---------------------------------------------------------

def test_synthetic_minimum_hp_root_movement_wins():

    open_notes = C_STANDARD.notes[1:]

    # A current HP no real E4 candidate could ever be inside.
    current_hp = HandPosition(30, 33)

    # No melody_phrase_notes at all -- see the previous test's
    # own comment for why this is the clean, reliable way to
    # guarantee a universal phrase-coverage tie here, isolating
    # hp_tiebreak's own movement comparison specifically.
    result = _choose_melody_position(
        64, open_notes, current_hp=current_hp,
        previous_position={"string": 0, "fret": 30, "score": 0}
    )

    # movement from root 30: fret16->14, fret9->21, fret5->25,
    # fret2->28 -- fret 16 has the smallest movement and must
    # win, even though it is E4's own WORST-scored candidate
    # overall (score -3, the lowest of all four).
    assert result["fret"] == 16
