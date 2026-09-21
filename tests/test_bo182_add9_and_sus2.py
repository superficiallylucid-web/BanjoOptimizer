"""
tests/test_bo182_add9_and_sus2.py

Regression tests for BO-182: a new chord quality, "add9"/"9"
(root, major 3rd, perfect 5th, 9th -- deliberately NO 7th),
added to both music.CHORD_QUALITIES and music.QUALITY_CODE_
TO_DISPLAY_NAME, same gap shape BO-121/BO-167/BO-181 already
documented for "o7"/"7#5"/"6"/"7b5".

Deliberate design decision, per the user's own reasoning: a
5-note chord (1, 3, 5, 7, 9) has no practical banjo voicing at
all (4-5 strings), so both "add9" and bare "9" -- two different
spellings the user reported seeing for what they consider the
same chord -- are mapped to the SAME, no-7th interval set, even
though "9" alone is conventionally a dominant 9th (WITH a minor
7th) in general music theory. This test file locks in that
choice as a real test, not just a comment, so a future session
doesn't mistake the omitted 7th for a bug.

Second, separate finding from this same BO: "sus2" was ALREADY
present in both tables before this BO touched anything --
confirmed directly, nothing needed adding. Included here as a
real regression test (not just a comment) so it stays working.
"""

import sys

sys.path.insert(0, '.')

import music

from models import Harmony

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import _select_chord_shape_for_harmony


def _get_chord_service():

    return ChordService(ChordLibrary())


# ---------------------------------------------------------
# 1 -- add9 / "9", both mapped to the same no-7th interval set
# ---------------------------------------------------------

def test_add9_and_9_both_added_to_chord_qualities():

    assert "add9" in music.CHORD_QUALITIES

    assert "9" in music.CHORD_QUALITIES


def test_add9_and_9_both_added_to_display_name_table():

    # BO-121/BO-167/BO-181's own confirmed gap: this second table
    # gates _select_chord_shape_for_harmony()'s own earliest
    # return independently of CHORD_QUALITIES.
    assert music.quality_code_to_display_name("add9") == "add9"

    assert music.quality_code_to_display_name("9") == "add9"


def test_add9_and_9_produce_identical_no_seventh_tones():

    # G root (pitch class 7): G, A (9th), B (major 3rd), D
    # (perfect 5th) -- no F/F# at all (no 7th, major or minor).
    add9_tones = music.chord_tones(7, "add9")

    nine_tones = music.chord_tones(7, "9")

    expected = sorted([7, 9, 11, 2])

    assert sorted(add9_tones) == expected

    assert sorted(nine_tones) == expected

    # The deliberate part: no minor 7th (5) or major 7th (6) --
    # this is what distinguishes this BO's own choice from the
    # conventional dominant-9th reading of bare "9".
    assert 5 not in add9_tones

    assert 5 not in nine_tones


def test_add9_produces_a_real_shape():

    tuning = get_tunings()["Double C"]

    service = _get_chord_service()

    harmony = Harmony(
        measure=1, root_pc=7, quality_code="add9", symbol="Gadd9"
    )

    shape, is_exception, exception_dict, quality_recognized = (
        _select_chord_shape_for_harmony(harmony, tuning, service)
    )

    assert quality_recognized is True

    assert shape is not None

    assert shape.shape != ""


def test_bare_9_produces_a_real_shape():

    tuning = get_tunings()["Double C"]

    service = _get_chord_service()

    harmony = Harmony(
        measure=1, root_pc=7, quality_code="9", symbol="G9"
    )

    shape, is_exception, exception_dict, quality_recognized = (
        _select_chord_shape_for_harmony(harmony, tuning, service)
    )

    assert quality_recognized is True

    assert shape is not None

    assert shape.shape != ""


# ---------------------------------------------------------
# 2 -- sus2 was already present; confirmed still working
# ---------------------------------------------------------

def test_sus2_was_already_present_and_still_works():

    assert "sus2" in music.CHORD_QUALITIES

    assert music.quality_code_to_display_name("sus2") == "sus2"

    tuning = get_tunings()["Double C"]

    service = _get_chord_service()

    harmony = Harmony(
        measure=1, root_pc=7, quality_code="sus2", symbol="Gsus2"
    )

    shape, is_exception, exception_dict, quality_recognized = (
        _select_chord_shape_for_harmony(harmony, tuning, service)
    )

    assert quality_recognized is True

    assert shape is not None

    assert shape.shape != ""
