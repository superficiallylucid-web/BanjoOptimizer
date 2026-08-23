"""
tests/test_melody_occurrences.py

Tests for fretboard.sounding_notes() and
find_melody_occurrences() -- detecting where a melody pitch
occurs anywhere in a chord shape (any sounding string), as
opposed to calculate_shape_metadata()'s top_note, which only
ever reports the highest-sounding note.

Expected values here are computed from the actual tuning notes
and shape frets (visible in each test's own arithmetic /
assertions), not guessed from shape text alone.
"""

from tunings import get_tunings

from fretboard import (
    sounding_notes,
    find_melody_occurrences,
    calculate_shape_metadata
)


OPEN_G = get_tunings()["Open G"]

DOUBLE_D = get_tunings()["Double D"]


# ---------------------------------------------------------
# 1 -- melody note found on the top string
# ---------------------------------------------------------

def test_melody_on_top_string():

    # Open G melody strings: D3(50) G3(55) B3(59) D4(62).
    # "0000" (all open) -> D3 G3 B3 D4. Top note is D4 (string
    # index 3, the 1st string) -- confirm the occurrence
    # matches calculate_shape_metadata's own top_note for the
    # same shape.
    occurrences = find_melody_occurrences(OPEN_G, "0000", "D")

    top_note_strings = [o for o in occurrences if o.name == "D4"]

    assert len(top_note_strings) == 1

    assert top_note_strings[0].string_index == 3

    _, top_note = calculate_shape_metadata(OPEN_G, "0000", 7, "")

    assert top_note == "D4"


# ---------------------------------------------------------
# 2 -- melody note found on an inner string (NOT top note)
# ---------------------------------------------------------

def test_melody_on_inner_string_not_top_note():

    # "0000": D3 G3 B3 D4. B is on string index 2 (the 2nd
    # string) -- neither the lowest nor the highest string.
    # top_note for this shape is D4, not B -- proving melody
    # matching is genuinely independent of top_note.
    occurrences = find_melody_occurrences(OPEN_G, "0000", "B")

    assert len(occurrences) == 1

    assert occurrences[0].string_index == 2

    assert occurrences[0].name == "B3"

    _, top_note = calculate_shape_metadata(OPEN_G, "0000", 7, "")

    assert top_note != "B3"

    assert top_note == "D4"


# ---------------------------------------------------------
# 3 -- melody note found on more than one string
# ---------------------------------------------------------

def test_melody_found_on_multiple_strings():

    # "5555" on Open G: each string +5 frets ->
    # D3+5=G3(55), G3+5=C4(60), B3+5=E4(64), D4+5=G4(67).
    # G appears twice: string index 0 (G3) and index 3 (G4).
    occurrences = find_melody_occurrences(OPEN_G, "5555", "G")

    assert len(occurrences) == 2

    string_indexes = {o.string_index for o in occurrences}

    assert string_indexes == {0, 3}

    names = {o.name for o in occurrences}

    assert names == {"G3", "G4"}


# ---------------------------------------------------------
# 4 -- melody note not present
# ---------------------------------------------------------

def test_melody_note_not_present():

    # "0000" sounds D3 G3 B3 D4 -- no F anywhere.
    occurrences = find_melody_occurrences(OPEN_G, "0000", "F")

    assert occurrences == []


# ---------------------------------------------------------
# 5 -- a muted string that would otherwise have matched
# ---------------------------------------------------------

def test_muted_string_never_matches():

    # Full "2012" sounds E3 G3 C4 E4 (two E's). Muting the
    # first one ("--012") must leave exactly the second E
    # (E4, string index 3) -- the muted string must never
    # appear as a match, even though it held a matching pitch
    # when it was sounding.
    full_occurrences = find_melody_occurrences(
        OPEN_G, "2012", "E"
    )

    assert len(full_occurrences) == 2

    muted_occurrences = find_melody_occurrences(
        OPEN_G, "--012", "E"
    )

    assert len(muted_occurrences) == 1

    assert muted_occurrences[0].string_index == 3

    assert muted_occurrences[0].name == "E4"


# ---------------------------------------------------------
# 6 -- open strings are handled correctly
# ---------------------------------------------------------

def test_open_strings_count_as_sounding():

    # Every string in "0000" is open (fret 0) -- all 4 must
    # still be reported as genuinely sounding notes.
    notes = sounding_notes(OPEN_G, "0000")

    assert len(notes) == 4

    assert [n.name for n in notes] == ["D3", "G3", "B3", "D4"]


# ---------------------------------------------------------
# 7 -- a tuning other than Open G
# ---------------------------------------------------------

def test_works_with_a_different_tuning():

    # Double D (aDADE): melody strings D3(50) A3(57) D4(62)
    # E4(64). "0000" -> D3 A3 D4 E4. A is an inner voice here
    # too (string index 1), not the top note (E4).
    occurrences = find_melody_occurrences(DOUBLE_D, "0000", "A")

    assert len(occurrences) == 1

    assert occurrences[0].string_index == 1

    assert occurrences[0].name == "A3"

    _, top_note = calculate_shape_metadata(
        DOUBLE_D, "0000", 2, ""
    )

    assert top_note == "E4"

    assert top_note != "A3"
