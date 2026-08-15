"""
tests/test_fretboard_diagram_fret_number.py

Regression tests for BO-19: MuseScore's "Fret Number" (XML
<fretOffset>) and "Visible frets" (XML <frets>) properties on
generated FretDiagrams.

XML encoding, confirmed by direct inspection of a real example
score (BO-19 Utilize Fret Number value to improve Fretboard
Diagrams Example Score.mscz) rather than inferred from property
names -- see score_generator.py's own _set_fret_diagram_content()
docstring for the full investigation:

- <frets> is MuseScore's "Visible frets" -- a SEPARATE property
  from <strings> ("Strings"), easy to confuse since both
  happened to read 4 in the example file. Always written as 4
  for every generated diagram now (BO-19's own explicit
  requirement, regardless of the actual fingering).

- <fretOffset> is MuseScore's "Fret Number" minus 1 (confirmed:
  a real example with <fretOffset>2</fretOffset> is the intended
  encoding for a shape whose lowest fret is 3 -- Fret Number is
  a 1-indexed display of a 0-indexed-from-the-nut offset). Left
  unset when the lowest FRETTED (non-open) value is 1 or there
  are no fretted strings at all -- the normal first-position
  display.

- Once <fretOffset> is set, each <dot fret="N"> becomes RELATIVE
  to it (N = absolute_fret - fretOffset), not absolute --
  confirmed directly against the same real example. Open strings
  are entirely unaffected either way -- their <marker> is always
  written the same way, regardless of fretOffset.
"""

import xml.etree.ElementTree as ET

from score_generator import _set_fret_diagram_content


def _build_and_decode(values):
    """
    Runs values through _set_fret_diagram_content() and decodes
    the result back into (fret_offset, frets, per_string) for
    easy assertions -- per_string maps string index to either
    an int (absolute fret, already adjusted for fretOffset) or
    "open".
    """

    fret_diagram = ET.Element("FretDiagram")

    wrote = _set_fret_diagram_content(fret_diagram, values)

    assert wrote, f"expected values {values} to be written"

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    fret_offset = (
        int(fret_offset_element.text)
        if fret_offset_element is not None
        else 0
    )

    frets_element = fret_diagram.find("{*}frets")

    frets = (
        int(frets_element.text) if frets_element is not None
        else None
    )

    per_string_absolute = {}

    for string_element in fret_diagram.iter():

        if string_element.tag.split("}")[-1] != "string":

            continue

        string_no = int(string_element.attrib["no"])

        dot = string_element.find("{*}dot")

        marker = string_element.find("{*}marker")

        if dot is not None:

            per_string_absolute[string_no] = (
                int(dot.attrib["fret"]) + fret_offset
            )

        elif marker is not None:

            per_string_absolute[string_no] = "open"

    return fret_offset, frets, per_string_absolute


# ---------------------------------------------------------
# 1 -- all-open fingering
# ---------------------------------------------------------

def test_all_open_fingering():

    fret_offset, frets, per_string = _build_and_decode(
        [0, 0, 0, 0]
    )

    assert fret_offset == 0

    assert frets == 4

    assert per_string == {0: "open", 1: "open", 2: "open", 3: "open"}


# ---------------------------------------------------------
# 2 -- lowest fretted position is 1: normal/default behavior
# ---------------------------------------------------------

def test_lowest_fret_1_uses_default_fret_number():

    fret_offset, frets, per_string = _build_and_decode(
        [0, 1, 2, 3]
    )

    assert fret_offset == 0, (
        "Fret Number must stay at its normal/default value "
        "(no <fretOffset>) when the lowest fretted position is 1"
    )

    assert frets == 4

    assert per_string == {0: "open", 1: 1, 2: 2, 3: 3}


# ---------------------------------------------------------
# 3 -- lowest fretted position is 2
# ---------------------------------------------------------

def test_lowest_fret_2_sets_fret_number():

    fret_diagram = ET.Element("FretDiagram")

    _set_fret_diagram_content(fret_diagram, [0, 2, 3, 4])

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    assert fret_offset_element is not None

    assert fret_offset_element.text == "1", (
        "lowest fret 2 -> Fret Number 2 -> fretOffset = "
        "Fret Number - 1 = 1"
    )

    fret_offset, frets, per_string = _build_and_decode(
        [0, 2, 3, 4]
    )

    assert frets == 4

    # Absolute positions preserved exactly, regardless of the
    # relative encoding used internally.
    assert per_string == {0: "open", 1: 2, 2: 3, 3: 4}


# ---------------------------------------------------------
# 4 -- lowest fretted position is 3
# ---------------------------------------------------------

def test_lowest_fret_3_sets_fret_number():

    fret_diagram = ET.Element("FretDiagram")

    _set_fret_diagram_content(fret_diagram, [0, 3, 4, 5])

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    assert fret_offset_element is not None

    assert fret_offset_element.text == "2", (
        "lowest fret 3 -> Fret Number 3 -> fretOffset = "
        "Fret Number - 1 = 2"
    )

    fret_offset, frets, per_string = _build_and_decode(
        [0, 3, 4, 5]
    )

    assert frets == 4

    assert per_string == {0: "open", 1: 3, 2: 4, 3: 5}


# ---------------------------------------------------------
# 5 -- open string plus higher frets (open strings must be
# ignored when determining the lowest fretted position, and
# their display must remain unaffected by fretOffset)
# ---------------------------------------------------------

def test_open_string_plus_higher_frets():

    fret_offset, frets, per_string = _build_and_decode(
        [0, 2, 4, 0]
    )

    assert fret_offset == 1  # lowest FRETTED value is 2, not 0

    assert frets == 4

    assert per_string == {0: "open", 1: 2, 2: 4, 3: "open"}

    # Open strings remain represented as open-string markers,
    # not converted into fretted positions at any point.
    fret_diagram = ET.Element("FretDiagram")

    _set_fret_diagram_content(fret_diagram, [0, 2, 4, 0])

    for string_no in (0, 3):

        string_element = None

        for element in fret_diagram.iter():

            if (
                element.tag.split("}")[-1] == "string"
                and element.attrib.get("no") == str(string_no)
            ):

                string_element = element

        assert string_element.find("{*}marker") is not None

        assert string_element.find("{*}dot") is None


# ---------------------------------------------------------
# 6 -- frets above 4 must remain visible (not disappear off a
# default first-position display) -- a realistic, practical
# shape (hand_span within what playability.py actually accepts,
# not an unrealistic wide stretch)
# ---------------------------------------------------------

def test_frets_above_4_remain_visible_via_fret_number():

    fret_offset, frets, per_string = _build_and_decode(
        [0, 5, 6, 7]
    )

    assert fret_offset == 4  # lowest fretted = 5 -> offset = 4

    assert frets == 4

    assert per_string == {0: "open", 1: 5, 2: 6, 3: 7}

    # Every fretted position must fall within the visible
    # window (fretOffset+1 .. fretOffset+frets) -- the whole
    # point of this property.
    window_start = fret_offset + 1

    window_end = fret_offset + frets

    for value in per_string.values():

        if value == "open":

            continue

        assert window_start <= value <= window_end, (
            f"fret {value} falls outside the visible window "
            f"[{window_start}, {window_end}]"
        )


# ---------------------------------------------------------
# 7 -- muted-string shapes are still correctly skipped (an
# existing BO-15 rule -- confirms this change didn't disturb it)
# ---------------------------------------------------------

def test_muted_string_shape_still_not_written():

    fret_diagram = ET.Element("FretDiagram")

    wrote = _set_fret_diagram_content(
        fret_diagram, [None, 2, 3, 0]
    )

    assert wrote is False

    assert len(list(fret_diagram)) == 0
