"""
recommendations.py

Group-level step for a set of recommended TuningResults.

A single TuningResult (from TuningAnalyzer.score_tuning) only
knows about itself, so it can't know which of its advantages
are actually shared by every other tuning it's being shown
alongside. That's a property of the group being displayed
together, not of any one tuning -- so it's handled here,
after scoring, rather than inside the scorer.

This does not change scoring, selection, or order. It only
moves already-computed advantages into shared_features when
every recommendation in the group has them in common.
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
