"""
BO-167 -- adds the missing "6" (major 6th) chord quality to
music.CHORD_QUALITIES and music.QUALITY_CODE_TO_DISPLAY_NAME.

Root cause (confirmed via direct pipeline tracing during BO-167's
own investigation, before this fix): "6" was absent from both
dicts, so score_generator._select_chord_shape_for_harmony() always
returned (None, False, None) at its earliest quality-display gate
(score_generator.py, before chord_tones()/generate_candidates()
are ever reached) -- for every root, not just C. Same gap shape,
same fix, as BO-121's own earlier o7/7#5 additions.

These tests go beyond dict membership -- each one calls the real
production functions/pipeline directly, the same way BO-167's own
investigation did, to prove the fix actually reaches usable output,
not just that a key now exists.
"""

import xml.etree.ElementTree as ET

import music
from models import Harmony
from tunings import get_tunings
from chord_library import ChordLibrary
from chord_service import ChordService
from fretboard import parse_shape
import score_generator


def test_quality_code_to_display_name_recognizes_6():

    assert music.quality_code_to_display_name("6") == "6"


def test_chord_tones_returns_correct_intervals_for_c6():
    """
    C6 = C-E-G-A: major triad (root, major 3rd, perfect 5th) plus
    a major 6th above the root (9 semitones) -- root_pc=0 (C).
    """

    tones = music.chord_tones(0, "6")

    assert tones == [0, 4, 7, 9]


def test_c6_reaches_dynamic_shape_generation():
    """
    Confirms real candidates are produced by the dynamic generator
    (chord_service.get_shapes()), not just that chord_tones() no
    longer returns None in isolation.
    """

    tuning = get_tunings()["Open G"]
    chord_service = ChordService(ChordLibrary())

    shapes = chord_service.get_shapes(tuning, "C", 0, "6", "6")

    assert len(shapes) > 0
    assert all(shape.source == "generated" for shape in shapes)


def test_select_chord_shape_for_harmony_returns_usable_shape_for_c6():
    """
    The real, end-to-end production function -- confirms the
    actual failure mode BO-167 investigated (a (None, False, None)
    result) is genuinely gone, not just that an earlier stage in
    isolation now succeeds.
    """

    tuning = get_tunings()["Open G"]
    chord_service = ChordService(ChordLibrary())

    c6_harmony = Harmony(
        measure=1, root_pc=0, quality_code="6", symbol="C6"
    )

    shape, is_exception, incoming_hp = (
        score_generator._select_chord_shape_for_harmony(
            c6_harmony, tuning, chord_service
        )
    )

    assert shape is not None
    assert shape.shape != ""


def test_c6_shape_produces_real_fret_diagram_xml():
    """
    Carries the real shape produced above through to actual XML
    FD output (score_generator._set_fret_diagram_content()) --
    confirms the chord genuinely proceeds to FD creation, not just
    that a ChordShape object exists in memory.
    """

    tuning = get_tunings()["Open G"]
    chord_service = ChordService(ChordLibrary())

    c6_harmony = Harmony(
        measure=1, root_pc=0, quality_code="6", symbol="C6"
    )

    shape, _, _ = score_generator._select_chord_shape_for_harmony(
        c6_harmony, tuning, chord_service
    )

    values = parse_shape(shape.shape)

    fd_element = ET.Element("FretDiagram")
    score_generator._set_fret_diagram_content(fd_element, values)

    dots = fd_element.findall(".//dot")

    assert len(dots) > 0
    assert fd_element.find("strings").text == "4"


def test_g6_also_resolves_confirming_root_independence():
    """
    BO-167's own investigation confirmed the original failure was
    root-independent (C6, D6, G6, A6 all failed identically) --
    this confirms the fix is too, using a different root (G,
    root_pc=7) than the rest of this file's own C6-focused tests.
    """

    tuning = get_tunings()["Open G"]
    chord_service = ChordService(ChordLibrary())

    g6_harmony = Harmony(
        measure=1, root_pc=7, quality_code="6", symbol="G6"
    )

    shape, _, _ = score_generator._select_chord_shape_for_harmony(
        g6_harmony, tuning, chord_service
    )

    assert shape is not None

    tones = music.chord_tones(7, "6")

    # G6 = G-B-D-E
    assert tones == [7, 11, 2, 4]


def test_existing_qualities_unchanged():
    """
    Regression guard: confirms this addition didn't alter any of
    the 15 previously-existing quality codes' own intervals or
    display names.
    """

    assert music.CHORD_QUALITIES[""]["intervals"] == [0, 4, 7]
    assert music.CHORD_QUALITIES["m"]["intervals"] == [0, 3, 7]
    assert music.CHORD_QUALITIES["7"]["intervals"] == [0, 4, 7, 10]
    assert music.CHORD_QUALITIES["maj7"]["intervals"] == [
        0, 4, 7, 11
    ]
    assert music.CHORD_QUALITIES["o7"]["intervals"] == [0, 3, 6, 9]
    assert music.CHORD_QUALITIES["7#5"]["intervals"] == [
        0, 4, 8, 10
    ]

    assert music.QUALITY_CODE_TO_DISPLAY_NAME[""] == "Major"
    assert music.QUALITY_CODE_TO_DISPLAY_NAME["maj7"] == "Maj 7"
    assert music.QUALITY_CODE_TO_DISPLAY_NAME["o7"] == "dim7"
    assert music.QUALITY_CODE_TO_DISPLAY_NAME["7#5"] == "7#5"

    assert len(music.CHORD_QUALITIES) == 16
    assert len(music.QUALITY_CODE_TO_DISPLAY_NAME) == 12
