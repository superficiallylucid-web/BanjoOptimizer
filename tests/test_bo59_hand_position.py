"""
tests/test_bo59_hand_position.py

Unit tests for the BO-59 Hand Position (HP) state machine
(hand_position.py). These test the pure state-machine functions
directly, against the finalized BO-59 specification -- not
against production melody/chord selection, which does not yet
consume this state at all (per BO-59's own explicit scope).
"""

import sys

sys.path.insert(0, '.')

from hand_position import (
    HandPosition,
    chord_hp_span,
    melody_note_hp,
    open_string_hp,
    nearest_new_hp
)


# ---------------------------------------------------------
# No HP before the first fretted note/chord
# ---------------------------------------------------------

def test_no_hp_before_first_fretted_event():

    assert open_string_hp(None) is None


def test_initial_open_strings_leave_hp_as_none():

    hp = None

    hp = open_string_hp(hp)

    hp = open_string_hp(hp)

    hp = open_string_hp(hp)

    assert hp is None


# ---------------------------------------------------------
# First fretted note establishes HP
# ---------------------------------------------------------

def test_first_fretted_note_establishes_hp():

    hp = melody_note_hp(None, 3)

    assert hp == HandPosition(3, 6)


def test_first_fretted_note_at_fret_one():

    hp = melody_note_hp(None, 1)

    assert hp == HandPosition(1, 4)


# ---------------------------------------------------------
# Fretted note inside current HP leaves it unchanged
# ---------------------------------------------------------

def test_fretted_note_inside_hp_unchanged():

    hp = HandPosition(2, 5)

    result = melody_note_hp(hp, 4)

    assert result == hp

    assert result is hp  # genuinely unchanged, not a new equal one


def test_fretted_note_at_hp_low_edge_unchanged():

    hp = HandPosition(2, 5)

    assert melody_note_hp(hp, 2) == hp


def test_fretted_note_at_hp_high_edge_unchanged():

    hp = HandPosition(2, 5)

    assert melody_note_hp(hp, 5) == hp


# ---------------------------------------------------------
# Fretted note outside current HP establishes a new one --
# above or below, no distinction between directions
# ---------------------------------------------------------

def test_fretted_note_above_hp_establishes_new_hp():

    hp = HandPosition(2, 5)

    result = melody_note_hp(hp, 7)

    assert result == HandPosition(7, 10)


def test_fretted_note_below_hp_establishes_new_hp():

    # Real, confirmed example from the finalized BO-59
    # specification's own clarification: current HP 8-11, a
    # note at fret 7 (below) establishes HP 7-10 -- the hand
    # cannot play a lower fret while retaining a higher HP.
    hp = HandPosition(8, 11)

    result = melody_note_hp(hp, 7)

    assert result == HandPosition(7, 10)


def test_note_one_fret_below_hp_still_establishes_new_hp():

    # Confirms there is no partial-overlap tolerance: even a
    # single fret below the current HP is "outside", not a
    # special near-miss case.
    hp = HandPosition(5, 8)

    result = melody_note_hp(hp, 4)

    assert result == HandPosition(4, 7)


# ---------------------------------------------------------
# Open strings leave an EXISTING hp unchanged too
# ---------------------------------------------------------

def test_open_string_leaves_existing_hp_unchanged():

    hp = HandPosition(2, 5)

    assert open_string_hp(hp) == hp

    assert open_string_hp(hp) is hp


def test_open_string_between_two_different_fretted_regions():

    # Real, confirmed case: Cousin Sally Brown / Double C,
    # measures 7-8 -- E4 establishes (2,5), an open D4 sits
    # between it and the next fretted note, C4 (which then
    # establishes a genuinely different HP). The open note
    # itself must show the PRECEDING hp, untouched.
    hp = melody_note_hp(None, 2)  # E4

    assert hp == HandPosition(2, 5)

    hp_at_open_note = open_string_hp(hp)  # D4, open

    assert hp_at_open_note == HandPosition(2, 5)

    hp = melody_note_hp(hp_at_open_note, 1)  # C4

    assert hp == HandPosition(1, 4)


# ---------------------------------------------------------
# Chords always reset HP, even when overlapping the previous one
# ---------------------------------------------------------

def test_chord_always_resets_hp_even_when_overlapping():

    # Real, confirmed case from the BO-59 trace: The Christmas
    # Song / Double D, measure 2 -- a C chord (HP 10-13) is
    # immediately followed by a Cmaj7 chord whose own lowest
    # fret (9) already lies WITHIN the prior HP -- yet the real,
    # already-validated output genuinely resets to a new HP
    # (9-12), never merely preserving the old one.
    c_shape = [None, None, 10, None]  # lowest=10, highest=10

    hp = chord_hp_span(c_shape)

    assert hp == HandPosition(10, 13)

    # A second chord whose own lowest fret (9) is inside the
    # prior HP (10,13) must still genuinely reset, not preserve.
    second_shape = [None, None, 9, None]

    hp = chord_hp_span(second_shape)

    assert hp == HandPosition(9, 12)

    assert hp != HandPosition(10, 13)


def test_normal_chord_hp():

    shape_values = [None, 2, 1, None]  # lowest=1, span=1

    hp = chord_hp_span(shape_values)

    assert hp == HandPosition(1, 4)


def test_five_fret_fd_exception():

    # A legitimate chord shape spanning more than 4 frets --
    # the HP must widen to cover the whole real span, not
    # truncate it to a normal 4-fret window.
    shape_values = [4, None, 8, None]  # lowest=4, highest=8

    hp = chord_hp_span(shape_values)

    assert hp == HandPosition(4, 8)


def test_normal_span_chord_does_not_trigger_five_fret_exception():

    shape_values = [3, 4, None, None]  # lowest=3, highest=4, span=1

    hp = chord_hp_span(shape_values)

    assert hp == HandPosition(3, 6)  # normal 4-fret HP, not widened


def test_all_open_chord_returns_none():

    shape_values = [0, None, 0, None]

    assert chord_hp_span(shape_values) is None


# ---------------------------------------------------------
# Multiple out-of-HP candidates: nearest-new-HP calculation
# ---------------------------------------------------------

def test_nearest_new_hp_picks_smallest_movement():

    hp = HandPosition(2, 5)

    nearest = nearest_new_hp(hp, [7, 12, 19])

    assert nearest == 7


def test_nearest_new_hp_symmetric_above_and_below():

    hp = HandPosition(5, 8)

    # fret 2 is 3 away (below); fret 9 is 4 away (above) --
    # nearer one should win regardless of direction.
    nearest = nearest_new_hp(hp, [2, 9])

    assert nearest == 2


def test_nearest_new_hp_with_no_established_hp():

    # No established HP at all -- nothing to measure distance
    # from; the function must not crash, and must return one of
    # the real candidates.
    nearest = nearest_new_hp(None, [5, 7, 12])

    assert nearest in [5, 7, 12]


# ---------------------------------------------------------
# The real CSB/gCGCD case in full, end to end
# ---------------------------------------------------------

def test_real_csb_gCGCD_g4_case():

    # Real, confirmed sequence leading up to the first G4 in
    # measure 7 (Cousin Sally Brown / Double C): G3(open) ->
    # A3@2 -> C4(open) -> E4@2 -> ... -> E4@4 (measure 6) ->
    # G4 (measure 7). Established HP going in is 2-5, set at
    # A3 and never genuinely left (E4@4 stays inside it).
    hp = None

    hp = open_string_hp(hp)  # G3

    hp = melody_note_hp(hp, 2)  # A3

    hp = open_string_hp(hp)  # C4

    hp = melody_note_hp(hp, 2)  # E4

    hp = melody_note_hp(hp, 4)  # E4, measure 6 -- still (2,5)

    assert hp == HandPosition(2, 5)

    # G4 at fret 5 (the target): remains within (2,5).
    g4_at_5 = melody_note_hp(hp, 5)

    assert g4_at_5 == HandPosition(2, 5)

    assert g4_at_5 is hp

    # G4 at fret 7 (current real BO-58 output): establishes a
    # genuinely new HP.
    g4_at_7 = melody_note_hp(hp, 7)

    assert g4_at_7 == HandPosition(7, 10)

    assert g4_at_7 != hp
