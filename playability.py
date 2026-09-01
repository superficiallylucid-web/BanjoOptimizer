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

from shape_ratings import AVOID_SHAPES

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


LEFTWARD_FRET_EXCESS_THRESHOLD = 2


def _has_leftward_fret_excess(values):
    """
    BO-132.3: true if any earlier (leftward) fretted position in
    the shape string exceeds a later (rightward) fretted
    position by more than LEFTWARD_FRET_EXCESS_THRESHOLD frets.

    IMPORTANT -- string numbering. This shape string's own
    left-to-right position order (index 0 = leftmost character)
    is BO's own internal string1...string4 (ascending pitch,
    confirmed throughout this project's own convention). The
    player's own real-world banjo numbering is the reverse
    (string1 = highest-pitched, closest to the floor; string4 =
    lowest-pitched, closest to the 5th string) -- so the
    player's own stated rule, "a higher-(player)-numbered string
    may not be fretted more than 2 frets above a lower-(player)-
    numbered string", translates to exactly this: an EARLIER
    (lower-index, leftward) position in this raw string may not
    exceed a LATER (higher-index, rightward) position by more
    than 2. Confirmed directly (BO-132.2) against two real
    examples using the player's own explicit string-by-string
    breakdown: "7470" (positions 0 vs 1: fret 7 vs fret 4, excess
    3) and "5502" (positions 0/1 vs 3: fret 5 vs fret 2, excess
    3) -- both match this exact direction precisely.

    This is a hard, physical rejection rule -- not a scoring
    preference -- because it can be technically fingered (often
    via a barre) while still being a poor practical choice; the
    player has confirmed this directly, including for "2552"
    specifically, which passes every other existing check here.

    Open strings never participate -- only pairs where BOTH
    positions are genuinely fretted (not open, not muted) are
    compared. A shape with 0 or 1 fretted position automatically
    passes, since there's no pair to compare at all.
    """

    fretted = [
        (index, value)
        for index, value in enumerate(values)
        if value is not None and value > 0
    ]

    for earlier_index in range(len(fretted)):

        earlier_position, earlier_fret = fretted[earlier_index]

        for later_index in range(
            earlier_index + 1, len(fretted)
        ):

            later_position, later_fret = fretted[later_index]

            if (
                earlier_fret - later_fret
                > LEFTWARD_FRET_EXCESS_THRESHOLD
            ):

                return True

    return False


def _has_interior_string_omitted(values):
    """
    BO-132.5: true if a muted (None) string occupies an
    INTERIOR position -- index 1 or index 2 in this raw shape
    string.

    IMPORTANT -- numbering, same translation established in
    BO-132.2/BO-132.3. Index 0 (leftmost char) = player's string
    4, index 3 (rightmost char) = player's string 1; indices 1
    and 2 are the player's own strings 3 and 2 -- the two
    interior strings.

    The player's own stated rule: a three-string shape (exactly
    one muted string) is permitted only when the omitted string
    is string 1 or string 4 (the two OUTER positions, index 0 or
    index 3). Omitting string 2 or string 3 (index 1 or index 2)
    is never permitted, regardless of how many strings are
    muted overall.

    A shape with no muted strings at all trivially passes (no
    interior position is None).
    """

    return values[1] is None or values[2] is None


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

    # shape_ratings.py -- a human-curated list of shapes to
    # avoid, checked before every algorithmic rule below.
    # Confirmed directly why this is needed rather than another
    # algorithmic rule: barre technique makes hand mechanics
    # depend on which specific strings/fingers are involved in a
    # way no simple formula reliably captures (e.g. "2225" is
    # not playable despite passing every existing algorithmic
    # check below unchanged; a technically-fingerable barre like
    # "2552" is a separate, deliberate case -- BO-132.3 blocks it
    # via the leftward-fret-excess rule below instead, since the
    # player considers it a poor practical choice regardless of
    # whether the barre itself is possible).
    if shape_text in AVOID_SHAPES:

        return PlayabilityResult(
            accepted=False,
            reason="Manually flagged as not playable",
            warnings=warnings,
            score=_score(values)
        )

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

    if _has_leftward_fret_excess(values):

        return PlayabilityResult(
            accepted=False,
            reason=(
                "A string closer to the palm is fretted too "
                "far above a string farther out -- a poor "
                "practical choice even if technically "
                "fingerable"
            ),
            warnings=warnings,
            score=_score(values)
        )

    if _has_interior_string_omitted(values):

        return PlayabilityResult(
            accepted=False,
            reason=(
                "An interior string is muted -- a three-string "
                "shape is only permitted when the omitted "
                "string is string 1 or string 4"
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
