"""
tests/test_bo140_1_additional_strong_alternatives.py

Focused tests for BO-140.4 (supersedes BO-140.1's own, earlier
5%-based version): an optional --alternatives flag exposes
additional, lower-ranked tunings beyond the default top 3, using
a deliberately different eligibility question than the primary
set's own "(Very close alternative...)" text.

Eligibility: candidate.combined_score > 0 -- an existing,
already-computed field, not a new score (BO-140.3's own
investigation, across six real songs). This is intentionally
NOT the same test as apply_confidence()'s 5% mechanism, which
remains completely unchanged and is still used, unmodified, for
the primary set's own close-alternative text.

select_additional_strong_alternatives() is tested directly here
(no CLI subprocess needed) using the real, already-computed
TuningResult objects from real songs, matching BO-140's own
established real-data investigation.
"""

import sys

sys.path.insert(0, '.')

sys.path.insert(0, 'tests')

from recommendations import (
    apply_shared_features, apply_confidence,
    select_additional_strong_alternatives
)

from test_bo49_playing_model_chord_quality import _load, _analyzer


def _get_results(song_filename):

    p = _load(f'scores/{song_filename}')

    analyzer = _analyzer(p)

    results = analyzer.analyze()

    return results["modern"]


# ---------------------------------------------------------
# 1 -- default output unaffected: select_additional_strong_
# alternatives() is simply never called when alternatives are
# not requested at all (verified at the CLI-wiring level in
# main.py directly, matching the BO-140.4 implementation
# report's own byte-for-byte diff) -- confirmed at the unit
# level here via max_additional=0 producing no results.
# ---------------------------------------------------------

def test_zero_max_additional_returns_empty():

    modern = _get_results('Moon River.mscz')

    additional = select_additional_strong_alternatives(
        modern[3:], 0
    )

    assert additional == []


# ---------------------------------------------------------
# 2/3 -- max_additional is genuinely respected
# ---------------------------------------------------------

def test_alternatives_1_exposes_at_most_one():

    modern = _get_results('The Christmas Song.mscz')

    additional = select_additional_strong_alternatives(
        modern[3:], 1
    )

    assert len(additional) <= 1


def test_alternatives_3_exposes_up_to_three():

    modern = _get_results('The Christmas Song.mscz')

    additional = select_additional_strong_alternatives(
        modern[3:], 3
    )

    assert len(additional) <= 3


# ---------------------------------------------------------
# 4 -- White Christmas: real, confirmed positive rank 4 (A
# Minor) is now eligible under combined_score > 0, though it
# failed the OLD 5% test.
# ---------------------------------------------------------

def test_white_christmas_positive_rank_4_is_shown():

    modern = _get_results('White Christmas.mscz')

    assert modern[3].combined_score > 0, (
        "Expected rank 4's own real, confirmed combined_score "
        "to be positive for this real song."
    )

    additional = select_additional_strong_alternatives(
        modern[3:], 3
    )

    assert len(additional) > 0

    assert additional[0].name == modern[3].name


# ---------------------------------------------------------
# 5/6 -- Moon River: real, confirmed negative rank 4 stops the
# additional section entirely.
# ---------------------------------------------------------

def test_moon_river_negative_rank_4_produces_no_additional():

    modern = _get_results('Moon River.mscz')

    assert modern[3].combined_score <= 0, (
        "Expected rank 4's own real, confirmed combined_score "
        "to be non-positive for this real song."
    )

    additional = select_additional_strong_alternatives(
        modern[3:], 3
    )

    assert additional == []


def test_stops_at_first_non_positive_does_not_skip_ahead():

    modern = _get_results('Moon River.mscz')

    # Confirmed real: every one of ranks 4-6 is negative for
    # this song, but even if a later rank were positive, the
    # rule must stop at the first failure, not search past it.
    additional = select_additional_strong_alternatives(
        modern[3:], 5
    )

    assert additional == []


# ---------------------------------------------------------
# 7 -- requesting more than exist does not fail
# ---------------------------------------------------------

def test_requesting_more_than_exist_does_not_fail():

    modern = _get_results('The Christmas Song.mscz')

    additional = select_additional_strong_alternatives(
        modern[3:], 999
    )

    assert len(additional) <= len(modern[3:])


# ---------------------------------------------------------
# 8 -- primary .confidence values are not mutated (the new
# function no longer touches apply_confidence() or any shared
# object at all, unlike BO-140.1's own, earlier version --
# confirmed directly here)
# ---------------------------------------------------------

def test_primary_confidence_unaffected_by_additional_call():

    modern = _get_results('The Christmas Song.mscz')

    top_3 = apply_shared_features(modern[:3])

    top_3 = apply_confidence(top_3)

    primary_confidence_before = [r.confidence for r in top_3]

    select_additional_strong_alternatives(modern[3:], 3)

    primary_confidence_after = [r.confidence for r in top_3]

    assert primary_confidence_before == primary_confidence_after


# ---------------------------------------------------------
# 9 -- the existing "(Very close alternative...)" mechanism
# (apply_confidence(), 5%) remains completely unchanged --
# still produces the same real values it always did, unrelated
# to combined_score entirely.
# ---------------------------------------------------------

def test_apply_confidence_mechanism_unchanged():

    modern = _get_results('White Christmas.mscz')

    top_3 = apply_shared_features(modern[:3])

    top_3 = apply_confidence(top_3)

    # Every result still has a real, non-None confidence value
    # -- the apply_confidence() mechanism itself is completely
    # unchanged (it is a pure presentation annotation over
    # already-computed scores, per its own docstring) by
    # removing fifth_string_transition_support().
    #
    # The original comment here claimed every one of the top 3
    # was a genuine near-tie under the existing 5% mechanism --
    # confirmed no longer true for Open G specifically (its own
    # confidence of ~6.43 exceeds 5% of its own score, ~5.61):
    # fifth_string_transition_support() was inflating G Minor's
    # own score (previously 2nd place), artificially narrowing
    # the real gap to Open G. With that bug removed, Open G is
    # correctly a clearer standout, not a near-tie -- confirmed
    # directly, not assumed.
    for result in top_3:

        assert result.confidence is not None

    open_g = next(r for r in top_3 if r.name == "Open G")

    assert open_g.confidence > 0.05 * open_g.score

    for result in top_3:

        if result.name == "Open G":

            continue

        assert result.confidence < 0.05 * result.score


# ---------------------------------------------------------
# Real-song coverage matching BO-140.3's own investigation
# ---------------------------------------------------------

def test_christmas_song_ranks_4_to_6_eligible():

    modern = _get_results('The Christmas Song.mscz')

    additional = select_additional_strong_alternatives(
        modern[3:], 3
    )

    assert len(additional) == 3


def test_my_favorite_things_rank_4_eligible():

    modern = _get_results('My Favorite Things.mscz')

    additional = select_additional_strong_alternatives(
        modern[3:], 3
    )

    assert len(additional) >= 1

    assert additional[0].name == modern[3].name


def test_gamboge_ranks_4_to_6_eligible():

    modern = _get_results('Gamboge.mscz')

    additional = select_additional_strong_alternatives(
        modern[3:], 3
    )

    assert len(additional) == 3


def test_cousin_sally_brown_ranks_4_to_5_eligible():

    modern = _get_results('Cousin Sally Brown.mscz')

    additional = select_additional_strong_alternatives(
        modern[3:], 3
    )

    assert len(additional) >= 2
