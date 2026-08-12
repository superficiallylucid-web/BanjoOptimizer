"""
tests/test_aureolin_fixes.py

Focused regression tests for two small parser fixes revealed
by the Aureolin investigation:

1. Quality-code normalization -- "(no5)" suffixes (source-
   instrument voicing annotations, not a different chord)
   stripped so the underlying quality is recognized.
2. <fretOffset> support -- fret-diagram decoding now accounts
   for diagrams drawn starting above the nut.

Uses the real Aureolin files where practical (skips gracefully
if not present locally, matching the pattern used elsewhere in
this project), plus direct unit tests of the two functions
themselves so the fixes are provable without needing the real
files.
"""

from pathlib import Path

import xml.etree.ElementTree as ET

from parser import normalize_quality_code, MuseScoreFile

from music import chord_tones


AUREOLIN_DADE_PATH = (
    Path(__file__).parent.parent / "Aureolin__Bm__aDADE__.mscz"
)

AUREOLIN_EADE_PATH = (
    Path(__file__).parent.parent / "Aureolin__Bm__aEADE__.mscz"
)


# ---------------------------------------------------------
# Fix 1 -- quality code normalization
# ---------------------------------------------------------

def test_normalize_strips_no5_suffix():

    assert normalize_quality_code("7(no5)") == "7"

    assert normalize_quality_code("m(no5)") == "m"


def test_normalize_leaves_other_codes_unchanged():

    for code in ["", "m", "7", "m7", "maj7", "mb5", "5", "sus2", "sus4"]:

        assert normalize_quality_code(code) == code


def test_normalized_quality_is_recognized_by_chord_tones():

    # Before the fix, "7(no5)"/"m(no5)" were unrecognized by
    # chord_tones() (returned None) -- confirmed by inspection
    # during the Aureolin investigation. After normalization,
    # the underlying quality is recognized correctly.
    assert chord_tones(9, normalize_quality_code("7(no5)")) == (
        chord_tones(9, "7")
    )

    assert chord_tones(9, normalize_quality_code("m(no5)")) == (
        chord_tones(9, "m")
    )


def test_real_aureolin_harmonies_are_normalized():

    if not AUREOLIN_DADE_PATH.exists():

        print(
            "SKIPPED: Aureolin__Bm__aDADE__.mscz not found "
            "locally"
        )

        return

    p = MuseScoreFile(AUREOLIN_DADE_PATH)

    p.open()
    p.read_time_signature()
    p.read_melody_notes()
    p.read_harmonies(6)

    symbols = {h.symbol for h in p.score.harmonies}

    quality_codes = {h.quality_code for h in p.score.harmonies}

    # The real, confirmed pre-fix symbols/codes must be gone.
    assert "A(7(no5))" not in symbols

    assert "A(m(no5))" not in symbols

    assert "7(no5)" not in quality_codes

    assert "m(no5)" not in quality_codes

    # The normalized versions must be present instead.
    assert "A7" in symbols

    assert "Am" in symbols

    # And tones must now actually be populated (previously
    # empty, since chord_tones() didn't recognize the raw
    # codes).
    a7_harmony = [h for h in p.score.harmonies if h.symbol == "A7"][0]

    assert a7_harmony.tones == chord_tones(9, "7")


# ---------------------------------------------------------
# Fix 2 -- fretOffset support
# ---------------------------------------------------------

def _fret_diagram_with_offset(offset, dots):
    """
    Build a minimal <FretDiagram> element for direct unit
    testing, without needing a real file. dots: list of
    (string_no, fret) tuples.
    """

    xml = (
        f'<FretDiagram><fretOffset>{offset}</fretOffset>'
        f'<fretDiagram>'
    )

    for string_no, fret in dots:

        xml += (
            f'<string no="{string_no}">'
            f'<dot fret="{fret}">normal</dot></string>'
        )

    xml += '</fretDiagram></FretDiagram>'

    return ET.fromstring(xml)


def test_decode_fret_diagram_applies_offset():

    p = MuseScoreFile(AUREOLIN_EADE_PATH)

    element = _fret_diagram_with_offset(
        3, [(0, 0), (1, 1), (2, 2), (3, 2)]
    )

    # string 0 is a dot at raw fret 0 -- with the fix, dots
    # always get the offset added, even a dot AT fret 0 (which
    # is different from an open/circle string -- a dot means a
    # finger is placed there, just at the diagram's own first
    # fret position).
    shape = p._decode_fret_diagram(element)

    assert shape == "3455"


def test_decode_fret_diagram_open_string_ignores_offset():

    p = MuseScoreFile(AUREOLIN_EADE_PATH)

    xml = (
        '<FretDiagram><fretOffset>3</fretOffset>'
        '<fretDiagram>'
        '<string no="0"><marker>circle</marker></string>'
        '<string no="1"><dot fret="1">normal</dot></string>'
        '<string no="2"><dot fret="2">normal</dot></string>'
        '<string no="3"><marker>circle</marker></string>'
        '</fretDiagram></FretDiagram>'
    )

    element = ET.fromstring(xml)

    shape = p._decode_fret_diagram(element)

    # Open strings (circle markers) must stay "0" regardless
    # of the offset -- only dots get it added.
    assert shape == "0450"


def test_decode_fret_diagram_no_offset_unchanged():

    p = MuseScoreFile(AUREOLIN_EADE_PATH)

    element = _fret_diagram_with_offset(
        0, [(0, 2), (1, 0), (2, 1), (3, 2)]
    )

    assert p._decode_fret_diagram(element) == "2012"


def test_real_aeade_shapes_match_offset_corrected_values():

    if not AUREOLIN_EADE_PATH.exists():

        print(
            "SKIPPED: Aureolin__Bm__aEADE__.mscz not found "
            "locally"
        )

        return

    p = MuseScoreFile(AUREOLIN_EADE_PATH)

    p.open()
    p.read_time_signature()
    p.read_melody_notes()
    p.read_harmonies(4)

    # Confirmed by hand (raw XML inspection) and by the earlier
    # investigation: measure 15 (A7) has fretOffset=3, and the
    # correctly-offset shape is 0455 -- which does spell a real
    # A7 (E3 C#4 G4 A4), unlike the pre-fix reading.
    a7 = [h for h in p.score.harmonies if h.measure == 15][0]

    assert a7.shape == "0455"

    # Measure 1 (Bm) has fretOffset=0 -- unaffected by the fix,
    # confirms the offset=0 case still works correctly.
    bm = [h for h in p.score.harmonies if h.measure == 1][0]

    assert bm.shape == "2202"
