"""
tests/test_chord_service_melody_ranking.py

Tests for melody-note matching as a real part of ChordService's
ranking (not the isolated reordering-algorithm tests in
test_chord_service_melody.py, which use synthetic fixtures --
these use the real ChordLibrary + ChordService pipeline against
real Open G data, now that verified shapes get top_note/
inversion metadata calculated for them).
"""

from tunings import get_tunings

from chord_library import ChordLibrary

from chord_service import ChordService

from fretboard import calculate_shape_metadata, find_melody_occurrences


OPEN_G = get_tunings()["Open G"]


def _service():

    lib = ChordLibrary()

    lib.load("banjo_chord_library - gDGBD Chord Shapes.csv")

    return ChordService(lib)


# ---------------------------------------------------------
# 1/2 -- matching shapes (verified or generated) rank before
# non-matching ones
# ---------------------------------------------------------

def test_matching_shapes_rank_before_non_matching():

    service = _service()

    shapes = service.get_shapes_for_melody(
        OPEN_G, "C", 0, "", "Major", "E"
    )

    # Every match must appear before every non-match. "Match"
    # here means the same thing get_shapes_for_melody() itself
    # now uses: does the shape sound E anywhere, not just as
    # the top note.
    seen_non_match = False

    for shape in shapes:

        is_match = bool(
            find_melody_occurrences(OPEN_G, shape.shape, "E")
        )

        if not is_match:

            seen_non_match = True

        elif seen_non_match:

            raise AssertionError(
                f"{shape.shape} matches but appears after a "
                "non-matching shape"
            )


# ---------------------------------------------------------
# 3 -- verified matching shape ranks before generated
# matching shape
# ---------------------------------------------------------

def test_verified_match_ranks_before_generated_match():

    service = _service()

    shapes = service.get_shapes_for_melody(
        OPEN_G, "C", 0, "", "Major", "E"
    )

    matching = [s for s in shapes if s.top_note == "E4"]

    assert matching[0].shape == "2012"

    assert matching[0].source == "verified"


# ---------------------------------------------------------
# 4 -- no melody note preserves verified-first ordering
# ---------------------------------------------------------

def test_no_melody_note_preserves_verified_first():

    service = _service()

    with_melody_none = service.get_shapes_for_melody(
        OPEN_G, "C", 0, "", "Major", None
    )

    without_melody = service.get_shapes(
        OPEN_G, "C", 0, "", "Major"
    )

    assert (
        [s.shape for s in with_melody_none]
        == [s.shape for s in without_melody]
    )

    assert with_melody_none[0].source == "verified"


# ---------------------------------------------------------
# 5 -- melody matching does not remove non-matching shapes
# ---------------------------------------------------------

def test_melody_matching_does_not_remove_shapes():

    service = _service()

    unfiltered = service.get_shapes(
        OPEN_G, "C", 0, "", "Major"
    )

    filtered_for_melody = service.get_shapes_for_melody(
        OPEN_G, "C", 0, "", "Major", "E"
    )

    assert (
        {s.shape for s in unfiltered}
        == {s.shape for s in filtered_for_melody}
    )

    assert len(unfiltered) == len(filtered_for_melody)


# ---------------------------------------------------------
# 6 -- library shapes receive correct top_note metadata
# ---------------------------------------------------------

def test_library_shapes_get_top_note_metadata():

    service = _service()

    shapes = service.get_shapes(OPEN_G, "C", 0, "", "Major")

    verified = [s for s in shapes if s.source == "verified"]

    assert len(verified) > 0

    for shape in verified:

        assert shape.top_note != ""

        assert shape.inversion != ""

    # The known reference shape, checked precisely.
    reference = [s for s in verified if s.shape == "2012"][0]

    assert reference.top_note == "E4"

    assert reference.inversion == "First inversion"


# ---------------------------------------------------------
# 7 -- muted strings do not incorrectly become the top note
# ---------------------------------------------------------

def test_muted_string_excluded_from_top_note():

    # "555--" mutes the 1st string (the highest-pitched open
    # string). If the mute were ignored, the top note would
    # wrongly come out as G4 (62 + 5); correctly excluded, it
    # should be E4 (the next-highest sounding string, 55 + 5).
    inversion, top_note = calculate_shape_metadata(
        OPEN_G, "555--", 0, ""
    )

    assert top_note == "E4"


# ---------------------------------------------------------
# 8 -- open strings are handled correctly (can be the top
# note, unlike muted strings)
# ---------------------------------------------------------

def test_open_string_can_be_top_note():

    # "0000": all open. The 1st string (open D4) is genuinely
    # the highest-sounding note here -- open strings must
    # still count, unlike muted ones.
    inversion, top_note = calculate_shape_metadata(
        OPEN_G, "0000", 7, ""
    )

    assert top_note == "D4"
