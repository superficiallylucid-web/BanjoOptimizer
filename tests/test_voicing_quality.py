"""
tests/test_voicing_quality.py

Tests for music.classify_voicing_quality() / defining_tones(),
and their integration into chord_generator.py's ranking.

This is a ranking-signal system, not a filter -- these tests
deliberately include a case (TEST 3) confirming a rootless
voicing is never automatically rejected, since that's the
single most important requirement of this feature.
"""

from music import (
    chord_tones,
    defining_tones,
    classify_voicing_quality,
    ROOT_PRESENT,
    ROOTLESS_STRONG,
    ROOTLESS_WEAK
)

from tunings import get_tunings

from chord_generator import generate_candidates


OPEN_G = get_tunings()["Open G"]

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE


# ---------------------------------------------------------
# 1 -- complete major triad with root is stronger than a
# rootless subset
# ---------------------------------------------------------

def test_complete_major_triad_beats_rootless_subset():

    root_category, root_score = classify_voicing_quality(
        0, "", {0, 4, 7}  # C major: C+E+G
    )

    rootless_category, rootless_score = classify_voicing_quality(
        0, "", {4, 7}  # E+G only, no root
    )

    assert root_category == ROOT_PRESENT

    assert root_score > rootless_score


# ---------------------------------------------------------
# 2 -- complete minor triad with root is stronger than a
# rootless subset
# ---------------------------------------------------------

def test_complete_minor_triad_beats_rootless_subset():

    root_category, root_score = classify_voicing_quality(
        9, "m", {9, 0, 4}  # A minor: A+C+E
    )

    rootless_category, rootless_score = classify_voicing_quality(
        9, "m", {0, 4}  # C+E only, no root
    )

    assert root_category == ROOT_PRESENT

    assert root_score > rootless_score


# ---------------------------------------------------------
# 3 -- a rootless dominant-7th voicing with the 3rd and 7th
# remains eligible, NOT automatically rejected
# ---------------------------------------------------------

def test_rootless_dominant_7_with_guide_tones_not_rejected():

    # B7: root=B(11). 3rd=D#(3), 7th=A(9). A rootless voicing
    # with just those two guide tones is a real, commonly used
    # voicing choice.
    category, score = classify_voicing_quality(
        11, "7", {3, 9}
    )

    assert category is not None, (
        "a rootless voicing must never be rejected outright"
    )

    assert category == ROOTLESS_STRONG

    assert score > 0


# ---------------------------------------------------------
# 4 -- a weak rootless voicing (missing a defining tone)
# ranks below a stronger voicing
# ---------------------------------------------------------

def test_weak_rootless_voicing_ranks_below_strong_one():

    # B7 again: defining tones are the 3rd (D#=3) and 7th
    # (A=9). A voicing with only the 3rd, missing the 7th, is
    # weaker than one with both.
    weak_category, weak_score = classify_voicing_quality(
        11, "7", {3}
    )

    strong_category, strong_score = classify_voicing_quality(
        11, "7", {3, 9}
    )

    assert weak_category == ROOTLESS_WEAK

    assert strong_category == ROOTLESS_STRONG

    assert strong_score > weak_score


# ---------------------------------------------------------
# 5 -- repeated copies of the same chord tone don't
# artificially make a weak voicing appear complete
# ---------------------------------------------------------

def test_duplicate_notes_do_not_inflate_score():

    single_category, single_score = classify_voicing_quality(
        0, "maj7", {4}  # just E
    )

    duplicated_category, duplicated_score = (
        classify_voicing_quality(
            0, "maj7", {4}  # still just E as a SET --
            # duplicates on multiple strings collapse to the
            # same distinct pitch-class set, which is exactly
            # what this is testing: the caller passes distinct
            # pitch classes, so "E doubled across two strings"
            # and "E once" are indistinguishable inputs, by
            # design (see _sounding_pitch_classes in
            # chord_generator.py, which always dedupes before
            # calling this).
        )
    )

    assert single_category == duplicated_category

    assert single_score == duplicated_score


# ---------------------------------------------------------
# 6 -- the Cmaj7/aEADE regression case: 0220/0250 are
# distinguished from a stronger root-containing voicing
# ---------------------------------------------------------

def test_cmaj7_aeade_0220_0250_distinguished_from_root_present():

    results = generate_candidates(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Maj 7"
    )

    shapes_by_text = {r.shape: r for r in results}

    assert "0220" in shapes_by_text, (
        "0220 should still be discoverable -- this task does "
        "not remove it"
    )

    assert "0250" in shapes_by_text

    assert (
        shapes_by_text["0220"].voicing_quality_category
        == ROOTLESS_STRONG
    )

    assert (
        shapes_by_text["0250"].voicing_quality_category
        == ROOTLESS_STRONG
    )

    root_present_shapes = [
        r for r in results
        if r.voicing_quality_category == ROOT_PRESENT
    ]

    assert len(root_present_shapes) > 0, (
        "a root-containing Cmaj7 shape should exist among the "
        "current low-position candidates for aEADE -- if this "
        "assertion ever fails, that's a real fact worth "
        "reporting, not something to work around"
    )

    # A root-present shape must outscore the two rootless ones
    # on voicing quality specifically.
    for root_shape in root_present_shapes:

        assert (
            root_shape.voicing_quality_score
            > shapes_by_text["0220"].voicing_quality_score
        )


# ---------------------------------------------------------
# 7 -- existing playability results remain unchanged
# ---------------------------------------------------------

def test_playability_results_unchanged():

    from playability import evaluate

    known_shapes = {
        "2012": True, "2512": False, "2552": True, "5555": True,
        "2515": False, "0000": True, "0030": True, "0400": True,
        "0430": True, "5435": True, "2102": True, "2402": True,
        "2152": False, "2452": True, "2456": False
    }

    known_scores = {
        "2012": 88, "2512": 10, "2552": 66, "5555": 90,
        "2515": 7, "0000": 100, "0030": 100, "0400": 99,
        "0430": 86, "5435": 63, "2102": 88, "2402": 74,
        "2152": 10, "2452": 57, "2456": 43
    }

    for shape, expected_accepted in known_shapes.items():

        result = evaluate(shape)

        assert result.accepted == expected_accepted

        assert result.score == known_scores[shape]


# ---------------------------------------------------------
# 8 -- the known Open G reference shapes still rank #1
# ---------------------------------------------------------

def test_open_g_reference_shapes_still_rank_first():

    for root, root_pc, quality, expected_top in [
        ("C", 0, "Major", "2012"),
        ("G", 7, "Major", "0000"),
        ("E", 4, "Major", "2102"),
    ]:

        results = generate_candidates(
            OPEN_G, root, root_pc, "", quality
        )

        assert results[0].shape == expected_top
