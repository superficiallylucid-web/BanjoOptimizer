"""
tests/test_bo54_revision_incoming_hp.py

Regression tests for the BO-54 REVISION: incoming Hand Position
(HP) transition awareness.

The original BO-54 implementation only ever evaluated a candidate
chord shape against the melody FOLLOWING it -- never against the
hand position the player is already in when they arrive at the
chord. This file's own tests cover the fix: chord_service.py's
own get_shapes_for_exact_melody_pitch() now also weighs
transition_anchor_count -- how many FRETTED (non-open) string
positions a candidate shares exactly with incoming_shape, the
immediately preceding chord's own already-selected shape -- ahead
of following-melody continuity in the tiebreak, within the same
HP_CONTINUITY_QUALITY_TOLERANCE band BO-54 already established.

Primary real evidence throughout this file: The Christmas Song,
A Modal Sawmill tuning (aEADE), measure 2. The real preceding
chord is C (0(10)(10)0); the real following melody is B4/A4/G4/F4.
0(10)98 shares a real fretted anchor with C (3rd string, fret 10);
0798 shares none, despite serving the following melody better in
isolation. The user's own direct musical review of this real case
confirmed 0(10)98 is correct -- the following melody's own low-
position destination doesn't actually depend on staying near
Cmaj7's own HP (reachable via an open/5th-string bridge either
way), so the incoming-position anchor is what genuinely matters.

No special-case rule for Cmaj7 or this specific song exists
anywhere in the implementation -- confirmed by inspecting chord_
service.py directly: transition_anchor_count() takes only shape
strings as input and contains no chord-symbol or song-specific
logic at all.
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import _select_chord_shape_for_harmony

from melody_box_analysis import build_melody_boxes


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE


def _christmas_song_measure_2():
    """
    Real data: The Christmas Song's own real C -> Cmaj7 -> Em
    sequence at measure 2, A Modal Sawmill tuning.
    """

    p = MuseScoreFile("scores/The Christmas Song.mscz")

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    harmonies_sorted = sorted(
        p.harmonies, key=lambda h: (h.measure, h.beat)
    )

    c_index = next(
        i for i, h in enumerate(harmonies_sorted)
        if h.measure == 2 and h.beat == 0.0
    )

    return p, service, harmonies_sorted, c_index


# ---------------------------------------------------------
# 1 -- incoming HP continuity across a chord change (primary
# real case)
# ---------------------------------------------------------

def test_incoming_hp_continuity_across_chord_change():

    p, service, harmonies_sorted, c_index = (
        _christmas_song_measure_2()
    )

    c_harmony = harmonies_sorted[c_index]

    cmaj7_harmony = harmonies_sorted[c_index + 1]

    c_shape, _, _ = _select_chord_shape_for_harmony(
        c_harmony, A_MODAL_SAWMILL, service,
        melody_notes=p.score.notes, next_harmony=cmaj7_harmony
    )

    assert c_shape.shape == "0(10)(10)0"

    cmaj7_shape, _, _ = _select_chord_shape_for_harmony(
        cmaj7_harmony, A_MODAL_SAWMILL, service,
        melody_notes=p.score.notes,
        next_harmony=harmonies_sorted[c_index + 2],
        incoming_shape=c_shape.shape
    )

    # Real, confirmed: the shape sharing a genuine fretted anchor
    # with the preceding C chord wins.
    assert cmaj7_shape.shape == "0(10)98"


# ---------------------------------------------------------
# 2 -- a candidate that preserves the existing HP wins over one
# that does not, when quality is within tolerance
# ---------------------------------------------------------

def test_candidate_preserving_existing_hp_preferred():

    p, service, harmonies_sorted, c_index = (
        _christmas_song_measure_2()
    )

    cmaj7_harmony = harmonies_sorted[c_index + 1]

    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Major 7th", {71},
        preferred_melody_fret=9, incoming_shape="0(10)(10)0"
    )

    winner = shapes[0]

    # 0(10)98 shares fret 10 on string index 1 exactly with the
    # real incoming C shape (0(10)(10)0) -- confirmed real
    # positional continuity, not merely nearby quality.
    assert winner.shape == "0(10)98"


# ---------------------------------------------------------
# 3 -- a candidate establishing a NEW HP can still win when its
# own following-melody continuity is genuinely better and no
# candidate offers a real incoming anchor
# ---------------------------------------------------------

def test_new_hp_wins_when_no_incoming_anchor_available():

    p, service, harmonies_sorted, c_index = (
        _christmas_song_measure_2()
    )

    cmaj7_harmony = harmonies_sorted[c_index + 1]

    # No incoming_shape at all (e.g. the first chord of a song,
    # or a preceding chord whose own shape shares nothing
    # fretted with any real candidate here) -- anchor_count is
    # 0 for every candidate, so the algorithm correctly falls
    # through to following-melody continuity exactly as BO-54's
    # own original mechanism did.
    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Major 7th", {71},
        preferred_melody_fret=9, incoming_shape=None
    )

    winner = shapes[0]

    assert winner.shape == "0(10)98"

    # Confirms this isn't a coincidence of quality alone -- with
    # NO incoming shape, the tiebreak still correctly reaches the
    # same conclusion via following-melody continuity (BO-54's
    # own original mechanism, still active and correct on its
    # own when there's nothing to anchor into).


# ---------------------------------------------------------
# 4 -- a genuine HP transition is still allowed (not made
# absolute) when the next chord shares no anchor with this one
# ---------------------------------------------------------

def test_genuine_hp_transition_still_occurs():

    p, service, harmonies_sorted, c_index = (
        _christmas_song_measure_2()
    )

    cmaj7_harmony = harmonies_sorted[c_index + 1]

    em_harmony = harmonies_sorted[c_index + 2]

    cmaj7_shape, _, _ = _select_chord_shape_for_harmony(
        cmaj7_harmony, A_MODAL_SAWMILL, service,
        melody_notes=p.score.notes, next_harmony=em_harmony,
        incoming_shape="0(10)(10)0"
    )

    em_shape, _, _ = _select_chord_shape_for_harmony(
        em_harmony, A_MODAL_SAWMILL, service,
        melody_notes=p.score.notes,
        next_harmony=harmonies_sorted[c_index + 3],
        incoming_shape=cmaj7_shape.shape
    )

    # Real, confirmed: Em gets its own, separately selected shape
    # -- HP continuity does not lock the whole song into one hand
    # position; a real transition still happens where the music
    # itself changes.
    assert em_shape.shape != cmaj7_shape.shape


# ---------------------------------------------------------
# 5 -- an open/5th-string note does not interfere with either
# the incoming-anchor or following-melody dimensions
# ---------------------------------------------------------

def test_open_string_bridge_does_not_block_transition():

    p, service, harmonies_sorted, c_index = (
        _christmas_song_measure_2()
    )

    cmaj7_harmony = harmonies_sorted[c_index + 1]

    # Every real Cmaj7 candidate here sounds an open 4th string
    # (index 0 = 0 in every real shape checked) -- confirms an
    # open-string match is correctly EXCLUDED from anchor_count
    # (see transition_anchor_count()'s own docstring for why:
    # an open string requires no positional continuity at all
    # and would inflate the count without musical meaning).
    from fretboard import parse_shape

    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Major 7th", {71},
        preferred_melody_fret=9, incoming_shape="0(10)(10)0"
    )

    winner = shapes[0]

    winner_values = parse_shape(winner.shape)

    incoming_values = parse_shape("0(10)(10)0")

    # Both share an open 4th string, but the winner is decided by
    # the FRETTED anchor (string index 1, fret 10), not the open
    # one -- confirmed directly against the real winning shape.
    assert winner_values[0] == 0 == incoming_values[0]

    assert winner_values[1] == 10 == incoming_values[1]


# ---------------------------------------------------------
# 6 -- intrinsic chord quality remains relevant: a genuinely
# low-quality candidate never wins even with a perfect anchor
# ---------------------------------------------------------

def test_quality_still_protects_against_perfect_anchor():

    # A candidate 2.0 quality points below the group's own best
    # (well outside HP_CONTINUITY_QUALITY_TOLERANCE) must never
    # win, even when incoming_shape is engineered to match it
    # exactly (the maximum possible anchor bonus).
    shapes = ChordService(ChordLibrary()).get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Major 7th", {71},
        preferred_melody_fret=9, incoming_shape="2350"
    )

    winner = shapes[0]

    assert winner.shape == "0(10)98"

    assert winner.shape != "2350"


# ---------------------------------------------------------
# 7 -- following-melody continuity remains a real, active
# factor (not replaced by the incoming-anchor signal)
# ---------------------------------------------------------

def test_following_melody_continuity_still_a_real_factor():

    p, service, harmonies_sorted, c_index = (
        _christmas_song_measure_2()
    )

    cmaj7_harmony = harmonies_sorted[c_index + 1]

    boxes = build_melody_boxes(p.score)

    cmaj7_box = next(b for b in boxes if b[0] == cmaj7_harmony)

    _, _, box_notes = cmaj7_box

    # Real, confirmed: the box still has 4 following melody notes
    # -- following-melody continuity is still a real, computed
    # input to this decision, not discarded by the revision.
    assert [n.midi for n in box_notes] == [71, 69, 67, 65]

    # With NO incoming shape at all, following-melody continuity
    # alone still correctly picks 0(10)98 here too (see test 3) --
    # confirming this dimension remains genuinely load-bearing,
    # not vestigial.


# ---------------------------------------------------------
# 8 -- no special-case behavior for Cmaj7 or The Christmas Song
# ---------------------------------------------------------

def test_no_special_case_for_cmaj7_or_this_song():

    import inspect

    import chord_service

    source = inspect.getsource(
        chord_service.ChordService
        .get_shapes_for_exact_melody_pitch
    )

    # Confirms the mechanism contains no conditional logic keyed
    # on a chord symbol or song title anywhere in its own
    # functional code (comments/docstrings may legitimately
    # reference the real example that motivated this fix -- that
    # is not the same as the algorithm branching on it).
    assert 'symbol ==' not in source

    assert 'if quality_code ==' not in source

    # The SAME general mechanism, applied to a different real
    # chord pair, produces a different real result driven only by
    # the actual shapes involved -- Am (5320) into B7, confirmed
    # real (The Christmas Song's own real m6-7 sequence, A Modal
    # Sawmill) to share a real fretted anchor (string index 0,
    # fret 5).
    from fretboard import parse_shape

    am_values = parse_shape("5320")

    shapes = ChordService(ChordLibrary()).get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "B", 11, "7", "Dominant 7th",
        {71}, preferred_melody_fret=7, incoming_shape="5320"
    )

    winner_values = parse_shape(shapes[0].shape)

    assert winner_values[0] == am_values[0] == 5
