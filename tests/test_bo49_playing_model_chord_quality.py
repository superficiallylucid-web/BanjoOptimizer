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

    _, quality_alone, _, _, _ = analyzer.chord_fd_quality_bonus(
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

    # Real, confirmed data: avg_awkwardness (the old BO-43/44/46
    # working-fret-only metric) no longer ties these two exactly
    # -- confirmed directly against this project's own
    # pre-BO-131.4 code (backed up before that change): Old G was
    # already 0.2 and Open C already 0.0857 before BO-131.4
    # touched anything (BO-131.4 never modifies avg_awkwardness's
    # own computation at all -- only adds a separate, new
    # accumulator alongside it). The old "exact tie at 0.2"
    # assumption was already stale for an unrelated, earlier
    # reason; this is not a BO-131.4 regression.
    #
    # The test's own point still stands even without the tie:
    # chord_fd_quality distinguishes these two tunings by more
    # than avg_awkwardness alone does, which the two assertions
    # below still directly demonstrate.
    #
    # Updated 0.1951219512195122 (from a stale 0.2) -- BO-167
    # (added the previously-unsupported "6" chord quality)
    # genuinely changed this value, confirmed directly: this song
    # contains a real D6 chord (measure 72) that, before BO-167,
    # got no shape at all (quality_code "6" was unrecognized) and
    # was silently skipped by this exact loop's own `if shape is
    # None: continue` (optimizer.py) -- never counted in
    # total_chord_onsets at all. BO-167 correctly gives it a real
    # shape now ("0445", working_fret 4, confirmed directly), which
    # is counted going forward. Confirmed via direct instrumentation
    # of this exact computation: awkwardness_sum is unchanged at
    # 8.0 (D6's own shape contributes 0 awkwardness -- its
    # working_fret doesn't exceed WORKING_FRET_COMFORT_CEILING);
    # only the denominator shifts, from 40 (D6 excluded) to 41 (D6
    # included) -- 8.0/40 = 0.2 (the old, stale value) and
    # 8.0/41 = 0.1951219512195122 (the new, correct one). This is
    # the intended, correct consequence of BO-167's own fix, not a
    # regression -- no other chord's own shape or contribution
    # changed.
    assert old_g.avg_awkwardness == 0.1951219512195122

    # Updated 0.0 (from a stale 0.08571428571428572) -- BO-131.11
    # (Rule A/B joint chord/melody selection) genuinely improved
    # one chord occurrence in this exact song/tuning, bringing
    # every chord in Open C to working_fret <= 7 (the real
    # WORKING_FRET_COMFORT_CEILING). Confirmed directly in
    # BO-131.11's own report as an intended behavioral
    # consequence of that change, not a regression -- the old
    # value predates BO-131.11 and is no longer what this
    # codebase actually produces.
    #
    # Updated again to 0.10810810810810811 (from that same 0.0)
    # -- BO-167 (added the previously-unsupported "6" chord
    # quality). Same root cause and same confirmation method as
    # the old_g update above: this song's real D6 chord (measure
    # 72) previously got no shape in Open C either (same "6"
    # quality gap, tuning-independent), so it was excluded from
    # this average entirely; BO-167 gives it a real shape now, and
    # that shape's own working_fret genuinely exceeds
    # WORKING_FRET_COMFORT_CEILING in this tuning specifically
    # (unlike in Old G, where D6's shape happens to contribute 0
    # awkwardness) -- confirmed directly: toggling "6" in/out of
    # music.CHORD_QUALITIES / QUALITY_CODE_TO_DISPLAY_NAME at
    # runtime, with no other change, reproduces exactly 0.0 (old)
    # and 0.10810810810810811 (new) via this exact TuningAnalyzer
    # path. Intended, correct consequence of BO-167's own fix, not
    # a regression -- BO-131.11's own finding above (every OTHER
    # chord in Open C already at working_fret <= 7) still holds;
    # D6 is a new, additional chord this average didn't include
    # before.
    assert open_c.avg_awkwardness == 0.10810810810810811

    assert old_g.avg_awkwardness != open_c.avg_awkwardness

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
