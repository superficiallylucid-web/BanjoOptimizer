"""
tests/test_bo48_chord_fd_tuning_selection.py

Regression tests for BO-48: Chord/FD-aware tuning selection.

Confirms the architecture BO-42 through BO-47 investigated:
  - Chord/FD quality is a SEPARATE term from PLAYING_MODEL_WEIGHT
    (a pre-existing, unrelated contribution).
  - Chord/FD quality is normalized against a FIXED reference
    (MAX_AWKWARDNESS_REFERENCE), not the current candidate set's
    own min/max -- confirmed via a direct normalization-
    invariance test, since this was BO-47's own central finding
    and requirement.
  - Unplayable melody notes receive a SEPARATE, explicit penalty,
    never diluted by Chord/FD influence.
  - influence=0.0 preserves melody-only ranking (apart from the
    separately-justified unplayable-note penalty).
  - influence=1.0 is a boundary condition only, not a recommended
    setting.
  - A substantial melody advantage remains dominant when Chord/FD
    is effectively tied (White Christmas, Open G vs. C Standard).

Real fixtures used: scores/Cousin Sally Brown.mscz, scores/My
Favorite Things.mscz, scores/The Christmas Song.mscz, scores/
White Christmas.mscz -- the four genuine, independent real scores
established across BO-45/46/47. scores/White Christmas (G
(gCGBD)).mscz is deliberately NOT used here -- confirmed in BO-46
to be a duplicate test-fixture path, not a fifth independent song.
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
# 1 -- normalization invariance (BO-47's central requirement)
# ---------------------------------------------------------

def test_chord_fd_quality_independent_of_candidate_set():

    p = _load('scores/The Christmas Song.mscz')

    analyzer = _analyzer(p)

    tuning = get_tunings()['Double D']

    # Compute Double D's own chord_fd_quality in isolation --
    # this method is per-tuning by construction, never given
    # other candidates at all.
    _, quality_alone, _, _ = analyzer.chord_fd_quality_bonus(
        tuning
    )

    # Compute it again via the full analyze() pipeline, where
    # Double D is being ranked alongside A Modal Sawmill and
    # Double C (a worse-chord-comfort candidate, per BO-47's own
    # real finding) and every other modern tuning.
    results = analyzer.analyze()

    double_d_result = next(
        r for r in results['modern'] if r.name == 'Double D'
    )

    assert double_d_result.chord_fd_quality == quality_alone, (
        "Double D's own Chord/FD quality must not change "
        "merely because other candidates are present in the "
        "group it's being ranked alongside -- this is the "
        "exact BO-47 defect this test exists to catch"
    )


def test_chord_fd_quality_stable_with_extreme_candidate_present():

    p = _load('scores/White Christmas.mscz')

    analyzer = _analyzer(p)

    tuning = get_tunings()['Old G']

    _, quality_alone, _, _ = analyzer.chord_fd_quality_bonus(
        tuning
    )

    results = analyzer.analyze()

    old_g_result = next(
        r for r in results['modern'] if r.name == 'Old G'
    )

    assert old_g_result.chord_fd_quality == quality_alone, (
        "an extreme candidate (Open G, avg_awkwardness > 3 in "
        "this song) being present in the same group must not "
        "shift Old G's own independently-computed Chord/FD "
        "quality"
    )


# ---------------------------------------------------------
# 2 -- influence = 0.0 preserves melody-only ranking
# ---------------------------------------------------------

def test_influence_zero_preserves_melody_ranking():

    p = _load('scores/The Christmas Song.mscz')

    analyzer = _analyzer(p)

    original_influence = analyzer.CHORD_FD_INFLUENCE

    original_penalty = analyzer.UNPLAYABLE_NOTE_PENALTY_WEIGHT

    try:

        analyzer.CHORD_FD_INFLUENCE = 0.0

        analyzer.UNPLAYABLE_NOTE_PENALTY_WEIGHT = 0.0

        results = analyzer.analyze()

        modern = results['modern']

        # With influence=0 and the unplayable penalty also
        # zeroed (isolating the Chord/FD contribution alone,
        # since it's a genuinely separate mechanism), the
        # combined_score ranking must match the raw melody
        # `score` ranking exactly.
        by_combined = [r.name for r in modern[:5]]

        by_melody = [
            r.name for r in
            sorted(modern, key=lambda r: -r.score)[:5]
        ]

        assert by_combined == by_melody

    finally:

        analyzer.CHORD_FD_INFLUENCE = original_influence

        analyzer.UNPLAYABLE_NOTE_PENALTY_WEIGHT = original_penalty


# ---------------------------------------------------------
# 3 -- influence = 1.0 boundary condition
# ---------------------------------------------------------

def test_influence_one_uses_chord_fd_quality_for_blend():

    p = _load('scores/The Christmas Song.mscz')

    analyzer = _analyzer(p)

    original_influence = analyzer.CHORD_FD_INFLUENCE

    original_penalty = analyzer.UNPLAYABLE_NOTE_PENALTY_WEIGHT

    try:

        analyzer.CHORD_FD_INFLUENCE = 1.0

        analyzer.UNPLAYABLE_NOTE_PENALTY_WEIGHT = 0.0

        results = analyzer.analyze()

        modern = results['modern']

        by_combined = [r.name for r in modern[:5]]

        by_chord_fd = [
            r.name for r in
            sorted(modern, key=lambda r: -r.chord_fd_quality)[:5]
        ]

        assert by_combined == by_chord_fd

        # Melody must still be available for diagnostics even
        # at influence=1.0 -- never overwritten or hidden.
        for r in modern:

            assert isinstance(r.score, float)

    finally:

        analyzer.CHORD_FD_INFLUENCE = original_influence

        analyzer.UNPLAYABLE_NOTE_PENALTY_WEIGHT = original_penalty


# ---------------------------------------------------------
# 4 -- melody remains dominant when Chord/FD is effectively
# tied (White Christmas, the strongest real BO-46/47 example)
# ---------------------------------------------------------

def test_white_christmas_melody_dominance_when_chord_fd_tied():

    p = _load('scores/White Christmas.mscz')

    analyzer = _analyzer(p)

    results = analyzer.analyze()

    top = results['modern'][0]

    assert top.name == 'Open G', (
        "Open G's own substantial real melody advantage should "
        "remain dominant at the production default influence, "
        "matching BO-46/47's own established finding"
    )


# ---------------------------------------------------------
# 5 -- unplayable-note penalty is separate from Chord/FD
# influence, and meaningfully improves Old G's own relative
# treatment (the real My Favorite Things case)
# ---------------------------------------------------------

def test_unplayable_note_penalty_improves_old_g_treatment():

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

    # Old G's own raw melody score is HIGHER than C Standard's
    # (confirmed real data) -- but its own combined_score must
    # not simply inherit that advantage once the separate
    # unplayable-note penalty is applied, since it has
    # meaningfully more unplayable notes.
    assert old_g.score > c_standard.score

    assert (
        c_standard.combined_score > old_g.combined_score
    ), (
        "C Standard's own fewer unplayable notes should be "
        "reflected in the final combined score, even though "
        "Old G's own raw melody score is higher"
    )


def test_unplayable_note_penalty_not_diluted_by_high_influence():

    p = _load('scores/My Favorite Things.mscz')

    analyzer = _analyzer(p)

    original_influence = analyzer.CHORD_FD_INFLUENCE

    try:

        # Even at full Chord/FD influence, a tuning's own
        # unplayable-note count must still meaningfully affect
        # its combined_score -- confirming this penalty is
        # genuinely separate from CHORD_FD_INFLUENCE, not folded
        # into (and therefore divided out by) it.
        analyzer.CHORD_FD_INFLUENCE = 1.0

        results = analyzer.analyze()

        old_g = next(
            r for r in results['modern'] if r.name == 'Old G'
        )

        assert old_g.unplayable_note_count == 18

        # The penalty (proportion * weight) must still be a
        # real, non-zero deduction from Old G's own combined
        # score at influence=1.0.
        raw_blend = old_g.chord_fd_quality

        assert old_g.combined_score < raw_blend, (
            "the unplayable-note penalty must still reduce "
            "Old G's own combined score even at full Chord/FD "
            "influence -- it must never be diluted by "
            "CHORD_FD_INFLUENCE"
        )

    finally:

        analyzer.CHORD_FD_INFLUENCE = original_influence


# ---------------------------------------------------------
# 6 -- Cousin Sally Brown (no chord data) gracefully handled
# ---------------------------------------------------------

def test_no_chord_data_produces_neutral_chord_fd_contribution():

    p = _load('scores/Cousin Sally Brown.mscz')

    analyzer = _analyzer(p)

    assert p.harmonies == []

    results = analyzer.analyze()

    for r in results['modern'][:5]:

        assert r.avg_awkwardness == 0.0

        assert r.chord_fd_quality == 1.0

        import math

        assert not math.isnan(r.combined_score)

    # With no chord data at all, the melody-only ranking must
    # be fully preserved (no arbitrary reordering from a
    # component that has nothing to discriminate on).
    by_combined = [r.name for r in results['modern'][:5]]

    by_melody = [
        r.name for r in
        sorted(results['modern'], key=lambda r: -r.score)[:5]
    ]

    assert by_combined == by_melody


# ---------------------------------------------------------
# 7 -- CHORD_FD_INFLUENCE is separate from PLAYING_MODEL_WEIGHT
# ---------------------------------------------------------

def test_chord_fd_influence_is_separate_constant():

    analyzer = TuningAnalyzer([], "Unknown")

    assert hasattr(analyzer, 'CHORD_FD_INFLUENCE')

    assert hasattr(analyzer, 'PLAYING_MODEL_WEIGHT')

    assert (
        analyzer.CHORD_FD_INFLUENCE
        != analyzer.PLAYING_MODEL_WEIGHT
    )

    assert 0.0 <= analyzer.CHORD_FD_INFLUENCE <= 1.0
