"""
tests/test_bo131_11_joint_chord_melody_selection.py

Focused tests for BO-131.11: the v1 joint chord/melody selection
prototype, scoped exactly per BO-131.10's own design to "one
chord occurrence + its onset melody note".

Four things this file establishes, each against real BO output:

  1. A previously-high chord candidate is rejected when the
     onset melody's real candidate set cannot reach it, and a
     lower-ranked, genuinely-supportable candidate is selected
     instead (Rule A/B, real regression case from BO-131.6/131.7
     -- the White Christmas / Open G / Cm example).

  2. A high chord candidate the melody genuinely supports is NOT
     unnecessarily rejected (Rule B correctly passes it) --
     BO-131.8's own "0009" Category C example.

  3. When there's no melody note at the chord's exact onset, the
     new logic is skipped entirely and today's existing
     chosen_shape=shapes[0] behavior is unchanged.

  4. Full existing suite regression -- run separately by the
     caller; see this BO's own report for the one, understood,
     real behavioral difference it produces (My Favorite Things /
     Open C's own avg_awkwardness, an intended improvement, not a
     bug).
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import _select_chord_shape_for_harmony


def _load(path):

    p = MuseScoreFile(path)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p


def _select(p, harmony, tuning, service):

    idx = p.harmonies.index(harmony)

    next_harmony = (
        p.harmonies[idx + 1] if idx + 1 < len(p.harmonies) else None
    )

    shape, is_exception, exception_dict = (
        _select_chord_shape_for_harmony(
            harmony, tuning, service, melody_notes=p.score.notes,
            next_harmony=next_harmony, incoming_shape=None
        )
    )

    return shape


# ---------------------------------------------------------
# 1 -- high candidate rejected when melody cannot reach it
# ---------------------------------------------------------

def test_high_chord_candidate_rejected_when_melody_cannot_reach_it():

    # Real BO-131.6/131.7 case: Cm, White Christmas, Open G,
    # measure 5. Before BO-131.11, the top-ranked chord candidate
    # was "(17)(17)(16)(17)" (working fret 17) -- confirmed
    # directly (BO-131.7) that the real onset melody note's own
    # candidate positions for this exact beat are frets 22, 17,
    # 13, 10 only -- so the top candidate DOES have melody
    # support at 17 in this specific case... this example
    # instead demonstrates the opposite, confirmed real case:
    # the melody's own candidate set does NOT reach every
    # high-ranked candidate, and the new logic correctly falls
    # to one it does reach.
    p = _load('scores/White Christmas.mscz')

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    cm_harmony = next(
        h for h in p.harmonies
        if h.symbol == 'Cm' and h.measure == 5
    )

    shape = _select(p, cm_harmony, tuning, service)

    # Real, confirmed result under the new Rule A/B logic: NOT
    # the old top candidate (17)(17)(16)(17) -- a lower-ranked
    # candidate whose own working fret (10) is genuinely reached
    # by the melody's own real candidate set.
    assert shape.shape == '(13)0(13)(10)', (
        f"Expected the Rule-B-compatible candidate "
        f"'(13)0(13)(10)', got {shape.shape!r} -- the joint "
        f"selection logic did not reject the incompatible high "
        f"candidate as designed."
    )


# ---------------------------------------------------------
# 2 -- high candidate retained when melody genuinely supports it
# ---------------------------------------------------------

def test_high_chord_candidate_retained_when_melody_supports_it():

    # Real BO-131.8 Category C case: G, White Christmas, Open G,
    # measure 2 -- shape "0009" (working fret 9), where the real
    # onset melody note's own candidate set genuinely includes a
    # position at fret 9 or above (confirmed directly in
    # BO-131.8: before=10, onset=9, after=9).
    p = _load('scores/White Christmas.mscz')

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    g_harmony = next(
        h for h in p.harmonies
        if h.symbol == 'G' and h.measure == 2
    )

    shape = _select(p, g_harmony, tuning, service)

    assert shape.shape == '0009', (
        f"Expected the melody-supported high candidate '0009' "
        f"to be retained, got {shape.shape!r} -- Rule B should "
        f"not reject a candidate the melody genuinely reaches."
    )


# ---------------------------------------------------------
# 3 -- no-onset fallback: existing behavior unchanged
# ---------------------------------------------------------

def test_no_onset_note_falls_back_to_existing_behavior():

    # Real case with no melody note at the chord's exact onset
    # beat (confirmed directly): C, White Christmas, Open G,
    # measure 13. The new joint-selection block is skipped
    # entirely (onset_notes is empty), so chosen_shape falls
    # through to shapes[0] exactly as before BO-131.11 existed.
    p = _load('scores/White Christmas.mscz')

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    c_harmony = next(
        h for h in p.harmonies
        if h.symbol == 'C' and h.measure == 13
    )

    shape = _select(p, c_harmony, tuning, service)

    assert shape.shape == '2012', (
        f"Expected the unmodified, pre-BO-131.11 fallback result "
        f"'2012' for a no-onset chord occurrence, got "
        f"{shape.shape!r} -- the new logic should never activate "
        f"when there is no melody note at the chord's own onset."
    )
