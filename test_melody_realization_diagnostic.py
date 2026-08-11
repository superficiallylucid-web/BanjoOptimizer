"""
tests/test_melody_realization_diagnostic.py

Tests for chord_service.diagnose_melody_realization() -- the
diagnostic that separates "is the melody note theoretically a
chord tone" from "does a playable shape actually put it
somewhere usable." Purely diagnostic; does not pick a
replacement chord or change any existing ranking.
"""

from tunings import get_tunings

from chord_library import ChordLibrary

from chord_service import (
    ChordService,
    diagnose_melody_realization,
    CHORD_TONE_AND_USABLE_VOICING,
    CHORD_TONE_BUT_NO_USABLE_VOICING,
    NOT_A_CHORD_TONE
)


OPEN_G = get_tunings()["Open G"]

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE


def _service():

    return ChordService(ChordLibrary())


# ---------------------------------------------------------
# 1 -- melody note is a chord tone AND available in a
# playable shape
# ---------------------------------------------------------

def test_chord_tone_with_usable_voicing():

    service = _service()

    shapes = service.get_shapes(OPEN_G, "C", 0, "", "Major")

    result = diagnose_melody_realization(
        OPEN_G, "C", 0, "", "E", shapes
    )

    assert result.category == CHORD_TONE_AND_USABLE_VOICING

    assert len(result.matches) > 0

    # The known reference shape should be among the matches.
    matching_shapes = {m.shape for m in result.matches}

    assert "2012" in matching_shapes


# ---------------------------------------------------------
# 2 -- melody note is a chord tone but no suitable playable
# shape (among the ones actually offered) contains it --
# real data: the top-2 ranked Cmaj7/aEADE shapes, melody B,
# the exact My Favorite Things scenario
# ---------------------------------------------------------

def test_chord_tone_but_no_usable_voicing():

    service = _service()

    shapes = service.get_shapes(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Maj 7"
    )

    top_two = shapes[:2]

    result = diagnose_melody_realization(
        A_MODAL_SAWMILL, "C", 0, "maj7", "B3", top_two
    )

    assert result.category == CHORD_TONE_BUT_NO_USABLE_VOICING

    assert result.matches == []


# ---------------------------------------------------------
# 3 -- melody note is not a chord tone at all
# ---------------------------------------------------------

def test_not_a_chord_tone():

    service = _service()

    shapes = service.get_shapes(OPEN_G, "C", 0, "", "Major")

    result = diagnose_melody_realization(
        OPEN_G, "C", 0, "", "D", shapes
    )

    assert result.category == NOT_A_CHORD_TONE

    assert result.matches == []


# ---------------------------------------------------------
# 4 -- an inner-string melody occurrence (not the top note)
# is correctly reported as a match
# ---------------------------------------------------------

def test_inner_string_occurrence_counts_as_a_match():

    service = _service()

    shapes = service.get_shapes(OPEN_G, "G", 7, "", "Major")

    # "0000" sounds D3 G3 B3 D4 -- B is an inner voice
    # (string index 2), NOT the top note (D4).
    result = diagnose_melody_realization(
        OPEN_G, "G", 7, "", "B", shapes
    )

    assert result.category == CHORD_TONE_AND_USABLE_VOICING

    inner_matches = [
        m for m in result.matches
        if m.shape == "0000" and m.string_index == 2
    ]

    assert len(inner_matches) == 1

    assert inner_matches[0].sounding_note == "B3"

    assert inner_matches[0].fret == 0


# ---------------------------------------------------------
# 5 -- a muted string cannot satisfy the match, even if it
# would have contained the requested pitch when sounding
# ---------------------------------------------------------

def test_muted_string_cannot_match():

    # Reuse the same muted-vs-full comparison established in
    # test_melody_occurrences.py: full "2012" sounds two E's;
    # muting the first ("--012") leaves only the second.
    service = _service()

    shapes = service.get_shapes(OPEN_G, "C", 0, "", "Major")

    full_result = diagnose_melody_realization(
        OPEN_G, "C", 0, "", "E", shapes
    )

    full_matches_for_2012 = [
        m for m in full_result.matches if m.shape == "2012"
    ]

    # 2012 sounds E3 and E4 -- both are legitimate pitch-class
    # matches for melody note "E".
    assert len(full_matches_for_2012) == 2

    # Directly check the muted variant isn't offered as a
    # match by constructing a single synthetic ChordShape for
    # it -- proving the diagnostic itself respects muting,
    # independent of whether the generator would ever produce
    # this specific shape.
    from models import ChordShape

    muted_shape = ChordShape(
        tuning="gDGBD", root="C", quality="Major",
        shape="--012", source="generated"
    )

    muted_result = diagnose_melody_realization(
        OPEN_G, "C", 0, "", "E", [muted_shape]
    )

    assert muted_result.category == CHORD_TONE_AND_USABLE_VOICING

    assert len(muted_result.matches) == 1

    # Only the remaining (non-muted) E should be found -- the
    # muted string's E must not appear.
    assert muted_result.matches[0].string_index == 3
