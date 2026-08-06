"""
playability.py

Rule-based playability filter for chord shapes.

First version: no machine learning, no user feedback -- just a
small set of explicit, explainable rules that accept or reject
a shape and produce a rough 0-100 playability score. Each rule
is a small, separate check, so later milestones (melody
matching, chord-transition analysis, comfort scoring, user
feedback) can add more rules or replace the scoring formula
without restructuring how results are reported.

Only evaluates the shape string itself (e.g. "2012", 4th string
to 1st, matching ChordShape.shape) -- it doesn't know or care
whether the shape came from the library or the generator.
chord_service.py decides who gets filtered.
"""

from models import PlayabilityResult


# A shape spanning more than this many frets (highest minus
# lowest, ignoring open strings) is rejected outright. 3 frets
# is a comfortable single-position stretch; 4+ is already a
# real reach.
MAX_ACCEPTABLE_SPAN = 3

# A span at exactly the acceptable limit still gets a warning,
# even though it's not rejected.
WARNING_SPAN = MAX_ACCEPTABLE_SPAN

# A string is flagged as an impossible "spike" if its fret is
# at least this much higher than BOTH neighboring strings --
# an isolated high fret sandwiched between two much lower
# ones, which requires fingers to cross over each other. This
# is the "2512" pattern from the design request: fret 5 on the
# 3rd string is 3 higher than the 2nd string (fret 2) and 4
# higher than the next string in (fret 1) on both sides.
SPIKE_THRESHOLD = 3


def _parse_shape(shape_text):

    return [int(char) for char in shape_text]


def _span(frets):

    return max(frets) - min(frets)


def _has_spike(frets):
    """
    True if any interior string's fret is at least
    SPIKE_THRESHOLD higher than BOTH its neighbors, AND both
    neighbors are themselves fretted (not open).

    The neighbor-fretted condition matters: an isolated high
    fret surrounded by OPEN strings isn't a crossing problem
    at all -- there's no competing finger nearby, it's just
    one finger on one string. The real problem is three (or
    more) simultaneous fingers where the middle one has to
    reach much farther than its neighbors, e.g. "2512": fret 5
    is sandwiched between frets 2 and 1, both of which also
    need a finger down at the same time.
    """

    for i in range(1, len(frets) - 1):

        fret = frets[i]

        left = frets[i - 1]
        right = frets[i + 1]

        if fret == 0 or left == 0 or right == 0:

            continue

        left_diff = fret - left
        right_diff = fret - right

        if (
            left_diff >= SPIKE_THRESHOLD
            and right_diff >= SPIKE_THRESHOLD
        ):

            return True

    return False


def _is_simple_barre(frets):
    """
    True if two or more ADJACENT strings share the same
    nonzero fret -- playable with one finger laid across just
    those strings.

    Adjacency matters: two non-adjacent strings happening to
    share a fret value isn't something one finger can span (a
    real finger can't skip over a different fret in between),
    so this only looks at consecutive string pairs.
    """

    for i in range(len(frets) - 1):

        if frets[i] == frets[i + 1] and frets[i] != 0:

            return True

    return False


def _score(frets):
    """
    Rough 0-100 playability estimate. Deliberately simple --
    meant to be refined by later milestones (comfort scoring,
    melody matching, user feedback), not to be the final word.
    """

    span = _span(frets)

    open_count = sum(1 for fret in frets if fret == 0)

    average_fret = sum(frets) / len(frets)

    score = 100

    score -= span * 10

    score -= average_fret * 4

    score += open_count * 5

    if _is_simple_barre(frets):

        score += 10

    if _has_spike(frets):

        score -= 40

    return max(0, min(100, round(score)))


def evaluate(shape_text):
    """
    Evaluate one chord shape (e.g. "2012") and return a
    PlayabilityResult.

    Only looks at the shape string itself -- no melody, no
    chord transitions, no comfort/user-feedback data. Those
    are future milestones layered on top of this, not part of
    this first version.
    """

    frets = _parse_shape(shape_text)

    warnings = []

    span = _span(frets)

    if _has_spike(frets):

        return PlayabilityResult(
            accepted=False,
            reason=(
                "Requires an isolated high fret between much "
                "lower frets on both sides -- likely "
                "impossible without crossing fingers over "
                "each other"
            ),
            warnings=warnings,
            score=_score(frets)
        )

    if span > MAX_ACCEPTABLE_SPAN:

        return PlayabilityResult(
            accepted=False,
            reason=(
                f"Fret span too wide ({span} frets) for a "
                "single comfortable hand position"
            ),
            warnings=warnings,
            score=_score(frets)
        )

    if span >= WARNING_SPAN:

        warnings.append(
            f"Noticeable stretch ({span} frets)"
        )

    if _is_simple_barre(frets):

        reason = "Simple barre shape, comfortable to play"

    elif sum(1 for fret in frets if fret == 0) >= 2:

        reason = "Compact shape with multiple open strings"

    else:

        reason = "Playable within a single hand position"

    return PlayabilityResult(
        accepted=True,
        reason=reason,
        warnings=warnings,
        score=_score(frets)
    )
