"""
tests/test_bo49_playing_model_chord_quality.py

Regression tests for BO-49: chord_fd_quality is now derived from
the existing Playing Model's own combined chord+melody phrase
scoring (analyze_tuning_playing_model()), not from avg_awkwardness
(working_fret) alone.

BO-49's own investigation (see optimizer.chord_fd_quality_bonus()'s
own docstring) found the Playing Model already does exactly what
BO-49 set out to build: for each real chord occurrence, evaluate
every candidate chord shape's own intrinsic playability (finger
count, span, hand geometry) TOGETHER with how well surrounding
melody notes can be played from that specific chord's own hand
position (contained-in-chord bonus, free-finger availability,
proximity to the chord's own working fret) -- composed into this
project's own richer chord/playing-quality signal, not a second,
parallel scoring system.

Confirmed with real data: White Christmas's own Open G has the
best raw melody score but the WORST Playing Model score among its
own real top candidates -- the "good melody, poor chords" case
BO-49 exists to catch, and something avg_awkwardness alone (BO-43
through BO-48) could never distinguish.

All 280 pre-existing tests (271 baseline + 9 BO-48 tests) continued
to pass unmodified against this change -- confirmed directly, not
assumed. BO-48's own established behaviors (White Christmas melody
dominance, My Favorite Things' unplayable-note treatment,
candidate-set-independent normalization, graceful no-chord-data
handling) all still hold under the richer metric.
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from optimizer import TuningAnalyzer

from tunings import get_tunings


def _load(path):

    p = MuseScoreFile(path)

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p


def _analyzer(p):

    return TuningAnalyzer(
        p.score.notes, p.score.key, p.harmonies, p.score.notes
    )


# ---------------------------------------------------------
# 1 -- a tuning with slightly BETTER melody but SUBSTANTIALLY
# worse chord/playing quality should not automatically win
# (Case A, White Christmas's own real Open G vs Old G pair)
# ---------------------------------------------------------

def test_better_chord_quality_narrows_a_real_melody_advantage():

    p = _load('scores/White Christmas.mscz')

    analyzer = _analyzer(p)

    results = analyzer.analyze()

    open_g = next(
        r for r in results['modern'] if r.name == 'Open G'
    )

    old_g = next(
        r for r in results['modern'] if r.name == 'Old G'
    )

    # Real, confirmed data: Open G has the better raw melody
    # score, but Old G has the better chord/playing quality --
    # the exact "good melody, poor chords" vs "less-perfect
    # melody, better chords" tension BO-49 exists to measure.
    assert open_g.score > old_g.score

    assert old_g.chord_fd_quality > open_g.chord_fd_quality

    # Open G's own real melody advantage here is large (~11
    # points, ~9%) -- genuinely "Case A: clearly superior
    # melody", so it correctly stays ahead even with worse
    # chord quality at the conservative default influence.
    assert open_g.combined_score > old_g.combined_score

    # But the gap should be meaningfully NARROWER on the
    # combined score than on raw melody alone -- confirming
    # chord/playing quality is genuinely pulling against Open
    # G's own advantage, not being ignored.
    raw_gap = open_g.score - old_g.score

    combined_gap_as_melody_units = (
        (open_g.combined_score - old_g.combined_score)
        / (1 - analyzer.CHORD_FD_INFLUENCE)
    )

    assert combined_gap_as_melody_units < raw_gap


# ---------------------------------------------------------
# 2 -- a tuning with slightly worse melody but substantially
# better chord/playing quality should be preferred when the
# melody gap is genuinely small (the best real approximation
# available in the 4-song dataset -- see this test's own
# honesty note below)
# ---------------------------------------------------------

def test_better_chord_quality_can_overcome_small_melody_gap():

    p = _load('scores/The Christmas Song.mscz')

    analyzer = _analyzer(p)

    results = analyzer.analyze()

    c_standard = next(
        r for r in results['modern'] if r.name == 'C Standard'
    )

    open_g = next(
        r for r in results['modern'] if r.name == 'Open G'
    )

    # HONESTY NOTE: this is the closest real "similar melody,
    # different chord quality" pair found across all 4 real
    # songs' own top-6 candidates (melody_gap=0.20, chord_gap=
    # 0.078) -- a genuinely SMALL melody gap, though the chord
    # gap itself is modest too, not dramatic. No real example
    # in the current 4-song dataset shows a large chord-quality
    # gap paired with a small melody gap; this test documents
    # the best available real evidence rather than a
    # constructed/synthetic case, per BO-49's own explicit
    # instruction not to manufacture a pair to force a result.
    assert abs(c_standard.score - open_g.score) < 1.0

    assert c_standard.chord_fd_quality > open_g.chord_fd_quality

    assert (
        c_standard.combined_score > open_g.combined_score
    ), (
        "with melody essentially tied, the tuning with better "
        "chord/playing quality should win, even at a modest "
        "quality gap"
    )


# ---------------------------------------------------------
# 3 -- melody and chord quality both similar: melody still
# provides useful tie-breaking information
# ---------------------------------------------------------

def test_melody_breaks_ties_when_chord_quality_is_similar():

    p = _load('scores/Cousin Sally Brown.mscz')

    analyzer = _analyzer(p)

    results = analyzer.analyze()

    a_minor = next(
        r for r in results['modern'] if r.name == 'A Minor'
    )

    a_modal = next(
        r for r in results['modern']
        if r.name == 'A Modal Sawmill'
    )

    # Both have chord_fd_quality=1.0 (no chord data at all for
    # this song -- the neutral default) -- an exact tie on
    # chord quality, so melody alone must decide.
    assert a_minor.chord_fd_quality == a_modal.chord_fd_quality

    assert a_minor.score > a_modal.score

    assert a_minor.combined_score > a_modal.combined_score


# ---------------------------------------------------------
# 4 -- the BO-48 unplayable-note penalty remains separate from
# the new, richer chord_fd_quality source
# ---------------------------------------------------------

def test_unplayable_note_penalty_still_separate_from_playing_model():

    p = _load('scores/My Favorite Things.mscz')

    analyzer = _analyzer(p)

    results = analyzer.analyze()

    old_g = next(
        r for r in results['modern'] if r.name == 'Old G'
    )

    c_standard = next(
        r for r in results['modern'] if r.name == 'C Standard'
    )

    assert old_g.unplayable_note_count == 18

    assert c_standard.unplayable_note_count == 12

    # Old G's own raw melody score is still higher than C
    # Standard's -- the unplayable-note penalty, not chord_fd_
    # quality, must still be what brings C Standard ahead
    # overall (confirmed unmodified from BO-48's own behavior).
    assert old_g.score > c_standard.score

    assert c_standard.combined_score > old_g.combined_score


# ---------------------------------------------------------
# 5 -- candidate-independence of the new Playing-Model-based
# chord_fd_quality (BO-47/48's own central requirement,
# reconfirmed for the new source)
# ---------------------------------------------------------

def test_playing_model_chord_quality_independent_of_candidate_set():

    p = _load('scores/The Christmas Song.mscz')

    analyzer = _analyzer(p)

    tuning = get_tunings()['Double D']

    _, quality_alone, _, _ = analyzer.chord_fd_quality_bonus(
        tuning
    )

    results = analyzer.analyze()

    double_d_result = next(
        r for r in results['modern'] if r.name == 'Double D'
    )

    assert double_d_result.chord_fd_quality == quality_alone, (
        "Double D's own chord_fd_quality (now Playing-Model-"
        "derived) must not change merely because other "
        "candidates are present in the group it's ranked "
        "alongside -- the same BO-47 invariant, reconfirmed "
        "for the new source"
    )


def test_playing_model_distinguishes_what_awkwardness_alone_cannot():

    p = _load('scores/My Favorite Things.mscz')

    analyzer = _analyzer(p)

    results = analyzer.analyze()

    old_g = next(
        r for r in results['modern'] if r.name == 'Old G'
    )

    open_c = next(
        r for r in results['modern'] if r.name == 'Open C'
    )

    # BO-54 REVISION note: avg_awkwardness no longer ties these
    # two exactly (0.20/0.20 as originally confirmed under BO-49)
    # -- both BO-54's original HP-continuity mechanism and its
    # revision changed which shape gets selected for some of
    # these chords, shifting the specific avg_awkwardness values
    # each time. This test's own core point doesn't depend on the
    # exact gap size (which keeps shifting for reasons unrelated
    # to this test's own purpose) -- it's that chord_fd_quality
    # (Playing-Model-derived, and completely independent of BO-54
    # 's own chord-shape-selection changes, since it uses its own
    # separate evaluate_combination()-based pipeline, confirmed
    # directly) still meaningfully distinguishes these two
    # candidates.

    # chord_fd_quality, now Playing-Model-derived, correctly
    # distinguishes them -- confirming this component genuinely
    # captures something (finger load, hand geometry, melody-
    # relative-to-chord positioning) avg_awkwardness alone
    # cannot see.
    assert open_c.chord_fd_quality != old_g.chord_fd_quality

    assert open_c.chord_fd_quality > old_g.chord_fd_quality


# ---------------------------------------------------------
# 6 -- regression: existing BO-48 behaviors all still hold
# ---------------------------------------------------------

def test_bo48_white_christmas_melody_dominance_still_holds():

    p = _load('scores/White Christmas.mscz')

    analyzer = _analyzer(p)

    results = analyzer.analyze()

    assert results['modern'][0].name == 'Open G'


def test_bo48_no_chord_data_still_gracefully_handled():

    p = _load('scores/Cousin Sally Brown.mscz')

    analyzer = _analyzer(p)

    assert p.harmonies == []

    results = analyzer.analyze()

    import math

    for r in results['modern'][:5]:

        assert r.chord_fd_quality == 1.0

        assert not math.isnan(r.combined_score)
