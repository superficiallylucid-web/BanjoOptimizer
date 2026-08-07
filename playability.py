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

Only evaluates the shape string itself (e.g. "2012", or "--657"
for a shape with a muted string -- see fretboard.parse_shape)
-- it doesn't know or care whether the shape came from the
library or the generator. chord_service.py decides who gets
filtered.
"""

from models import PlayabilityResult

from fretboard import (
    parse_shape,
    hand_span,
    average_fret as fretted_average
)


# A shape spanning more than this many FRETTED notes (open and
# muted strings don't count -- see fretboard.hand_span) is
# rejected outright. 3 frets is a comfortable single-position
# stretch; 4+ is already a real reach.
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


def _has_spike(values):
    """
    True if any interior string's fret is at least
    SPIKE_THRESHOLD higher than BOTH its neighbors, AND both
    neighbors are themselves fretted (not open or muted).

    The neighbor-fretted condition matters: an isolated high
    fret surrounded by OPEN or MUTED strings isn't a crossing
    problem at all -- there's no competing finger nearby,
    it's just one finger on one string. The real problem is
    three (or more) simultaneous fingers where the middle one
    has to reach much farther than its neighbors, e.g. "2512":
    fret 5 is sandwiched between frets 2 and 1, both of which
    also need a finger down at the same time.
    """

    for i in range(1, len(values) - 1):

        fret = values[i]

        left = values[i - 1]
        right = values[i + 1]

        if fret is None or fret == 0:

            continue

        if left is None or left == 0:

            continue

        if right is None or right == 0:

            continue

        left_diff = fret - left
        right_diff = fret - right

        if (
            left_diff >= SPIKE_THRESHOLD
            and right_diff >= SPIKE_THRESHOLD
        ):

            return True

    return False


def _is_simple_barre(values):
    """
    True if two or more ADJACENT strings share the same
    nonzero fret -- playable with one finger laid across just
    those strings.

    Adjacency matters: two non-adjacent strings happening to
    share a fret value isn't something one finger can span (a
    real finger can't skip over a different fret in between),
    so this only looks at consecutive string pairs. A muted
    string never counts as part of a barre.
    """

    for i in range(len(values) - 1):

        a = values[i]
        b = values[i + 1]

        if a is None or b is None:

            continue

        if a == b and a != 0:

            return True

    return False


def _score(values):
    """
    Rough 0-100 playability estimate. Deliberately simple --
    meant to be refined by later milestones (comfort scoring,
    melody matching, user feedback), not to be the final word.

    Open strings get a real bonus (they cost nothing to play).
    Muted strings do NOT get the same bonus -- deliberately
    silencing a string takes extra technique, unlike an open
    string ringing on its own -- so a muted string only gets a
    small, separate bonus, smaller than an open string's.
    """

    span = hand_span(values)

    open_count = sum(1 for value in values if value == 0)

    muted_count = sum(1 for value in values if value is None)

    avg = fretted_average(values)

    score = 100

    score -= span * 10

    score -= avg * 4

    score += open_count * 5

    score += muted_count * 2

    if _is_simple_barre(values):

        score += 10

    if _has_spike(values):

        score -= 40

    return max(0, min(100, round(score)))


def evaluate(shape_text):
    """
    Evaluate one chord shape (e.g. "2012", or "--657" with a
    muted string) and return a PlayabilityResult.

    Only looks at the shape string itself -- no melody, no
    chord transitions, no comfort/user-feedback data. Those
    are future milestones layered on top of this, not part of
    this first version.
    """

    values = parse_shape(shape_text)

    warnings = []

    span = hand_span(values)

    if _has_spike(values):

        return PlayabilityResult(
            accepted=False,
            reason=(
                "Requires an isolated high fret between much "
                "lower frets on both sides -- likely "
                "impossible without crossing fingers over "
                "each other"
            ),
            warnings=warnings,
            score=_score(values)
        )

    if span > MAX_ACCEPTABLE_SPAN:

        return PlayabilityResult(
            accepted=False,
            reason=(
                f"Fret span too wide ({span} frets) for a "
                "single comfortable hand position"
            ),
            warnings=warnings,
            score=_score(values)
        )

    if span >= WARNING_SPAN:

        warnings.append(
            f"Noticeable stretch ({span} frets)"
        )

    open_count = sum(1 for value in values if value == 0)

    if _is_simple_barre(values):

        reason = "Simple barre shape, comfortable to play"

    elif open_count >= 2:

        reason = "Compact shape with multiple open strings"

    else:

        reason = "Playable within a single hand position"

    return PlayabilityResult(
        accepted=True,
        reason=reason,
        warnings=warnings,
        score=_score(values)
    )
