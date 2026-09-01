"""
tests/test_bo132_5_three_string_shapes.py

Focused tests for BO-132.5: permitting valid three-string chord
shapes (exactly one muted string, on the outer position only)
and correctly rendering them in the generated MuseScore output.

Numbering, established BO-132.2/132.3: the raw shape string's
own left-to-right position order is identical to the player's
own 4-3-2-1 notation; only the LABEL differs. Index 0 (leftmost)
= player's string 4, index 3 (rightmost) = player's string 1,
indices 1/2 = player's interior strings 3/2.
"""

import sys

import xml.etree.ElementTree as ET

sys.path.insert(0, '.')

from playability import evaluate

from fretboard import parse_shape, format_shape

from score_generator import _set_fret_diagram_content


# ---------------------------------------------------------
# Valid three-string shapes (outer omission only)
# ---------------------------------------------------------

def test_omit_string_4_accepted():

    # --314: string4 (index0, leftmost) omitted. Real,
    # already-generated A Modal Sawmill G# Major candidate
    # (BO-132.4).
    result = evaluate('--314')

    assert result.accepted is True, (
        f"'--314' (string 4 omitted) should be accepted, got "
        f"accepted=False: {result.reason!r}"
    )


def test_omit_string_1_accepted():

    # 314-: string1 (index3, rightmost) omitted -- the mirror
    # case of --314.
    result = evaluate('314-')

    assert result.accepted is True, (
        f"'314-' (string 1 omitted) should be accepted, got "
        f"accepted=False: {result.reason!r}"
    )


# ---------------------------------------------------------
# Invalid interior omission
# ---------------------------------------------------------

def test_omit_string_3_rejected():

    # 4-14: string3 (index1) omitted -- interior, prohibited.
    result = evaluate('4-14')

    assert result.accepted is False, (
        "'4-14' (interior string 3 omitted) should be rejected."
    )

    assert 'interior' in result.reason.lower()


def test_omit_string_2_rejected():

    # 43-4: string2 (index2) omitted -- interior, prohibited.
    result = evaluate('43-4')

    assert result.accepted is False, (
        "'43-4' (interior string 2 omitted) should be rejected."
    )

    assert 'interior' in result.reason.lower()


# ---------------------------------------------------------
# Existing four-string behavior preserved
# ---------------------------------------------------------

def test_existing_four_string_shape_unaffected():

    result = evaluate('5550')

    assert result.accepted is True, (
        f"'5550' (ordinary four-string shape, no muted strings) "
        f"should still be accepted, got accepted=False: "
        f"{result.reason!r}"
    )


# ---------------------------------------------------------
# Parsing/formatting round-trip
# ---------------------------------------------------------

def test_mute_representation_round_trip():

    values = parse_shape('--314')

    assert values == [None, 3, 1, 4]

    assert format_shape(values) == '--314'


# ---------------------------------------------------------
# MuseScore output
# ---------------------------------------------------------

def test_muted_string_produces_cross_marker_in_output():

    fret_diagram_element = ET.Element("FretDiagram")

    values = parse_shape('--314')

    wrote = _set_fret_diagram_content(fret_diagram_element, values)

    assert wrote is True, (
        "A three-string shape with an outer string muted should "
        "now be written, not skipped."
    )

    string_elements = fret_diagram_element.find(
        "{*}fretDiagram"
    ).findall("{*}string")

    muted_string_element = string_elements[0]

    marker_element = muted_string_element.find("{*}marker")

    assert marker_element is not None, (
        "The muted string's own <string> element should contain "
        "a <marker> child."
    )

    assert marker_element.text == "cross", (
        f"Expected MuseScore's own mute-marker convention "
        f"'cross', got {marker_element.text!r}."
    )

    # The three genuinely fretted strings should still be
    # written normally, unaffected.
    for index, expected_fret in [(1, 3), (2, 1), (3, 4)]:

        dot_element = string_elements[index].find("{*}dot")

        assert dot_element is not None

        assert int(dot_element.get("fret")) == expected_fret


# ---------------------------------------------------------
# A real chord case: three-string candidate now survives the
# playability gate
# ---------------------------------------------------------

def test_real_g_sharp_major_three_string_candidate_survives():

    # BO-132.4's own real case: A Modal Sawmill, G# Major.
    # --314 is a real, generated candidate (source="generated")
    # that previously would have been structurally valid at the
    # playability layer already (no leftward-fret-excess
    # violation) -- this confirms it's still accepted now that
    # the interior-omission rule exists alongside it, since it
    # only omits the OUTER string.
    from chord_service import ChordService

    from chord_library import ChordLibrary

    from tunings import get_tunings

    service = ChordService(ChordLibrary())

    tuning = get_tunings()['A Modal Sawmill']

    shapes = service.get_shapes(tuning, 'G#', 8, '', 'Major')

    matching = [s for s in shapes if s.shape == '--314']

    assert len(matching) == 1, (
        "'--314' should still be a real, generated candidate "
        "for G# Major in A Modal Sawmill."
    )

    result = evaluate(matching[0].shape)

    assert result.accepted is True, (
        f"'--314' should pass the playability gate (outer "
        f"string omitted only), got accepted=False: "
        f"{result.reason!r}"
    )
