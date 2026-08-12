"""
recommendations.py

Group-level steps for a set of recommended TuningResults.

A single TuningResult (from TuningAnalyzer.score_tuning) only
knows about itself, so it can't know which of its advantages
are actually shared by every other tuning it's being shown
alongside, or how close its score is to theirs. Those are
properties of the group being displayed together, not of any
one tuning -- so they're handled here, after scoring, rather
than inside the scorer.

Neither function here changes scoring, selection, or order.
apply_shared_features() moves already-computed advantages into
shared_features when every recommendation in the group has
them in common. apply_confidence() computes each result's
score gap to its nearest neighbor in the group, for flagging
genuine near-ties in the report.
"""


def apply_shared_features(results):
    """
    Given a list of TuningResults being shown together,
    find advantages common to every one of them, move those
    into each result's shared_features, and remove them from
    each result's advantages so what's left is what actually
    distinguishes that recommendation from the others.

    Mutates and returns the same list -- doesn't change its
    order or which results are in it.
    """

    if not results:

        return results

    advantage_sets = [
        set(result.advantages)
        for result in results
    ]

    shared = advantage_sets[0]

    for advantage_set in advantage_sets[1:]:

        shared &= advantage_set

    # Preserve original order from the first result rather
    # than an arbitrary set order.
    shared_features = [
        advantage
        for advantage in results[0].advantages
        if advantage in shared
    ]

    for result in results:

        result.shared_features = shared_features

        result.advantages = [
            advantage
            for advantage in result.advantages
            if advantage not in shared
        ]

    return results


def apply_confidence(results):
    """
    Given a list of TuningResults being shown together (already
    sorted by score, highest first -- the order this project's
    scoring produces and this function relies on but never
    changes), compute each result's confidence: the score gap
    to its nearest neighbor (the previous or next result) in
    this SAME shown group.

    A small gap means a near-tie with another option actually
    being shown alongside it; a large gap means a clear
    standout. This is purely a presentation annotation over
    already-computed scores -- it does not change score, order,
    or which results are selected.

    confidence is left None for a single-result group (nothing
    to compare against) or if scoring produced fewer than 2
    results.
    """

    if len(results) < 2:

        for result in results:

            result.confidence = None

        return results

    for index, result in enumerate(results):

        gaps = []

        if index > 0:

            gaps.append(
                abs(result.score - results[index - 1].score)
            )

        if index + 1 < len(results):

            gaps.append(
                abs(result.score - results[index + 1].score)
            )

        result.confidence = min(gaps)

    return results
