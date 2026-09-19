"""
tests/test_bo181_unrecognized_chord_handling.py

Regression tests for BO-181, two parts:

1. A new chord quality, "7b5" (dominant 7th, flat 5 -- root,
   major 3rd, diminished 5th, minor 7th), added to both music.
   CHORD_QUALITIES and music.QUALITY_CODE_TO_DISPLAY_NAME (a
   second, separate lookup table that gates
   _select_chord_shape_for_harmony()'s own earliest return
   independently of CHORD_QUALITIES -- confirmed necessary by
   direct code reading, same gap shape BO-121/BO-167 already
   documented for "o7"/"7#5"/"6"). Real user-reported case:
   "G7b5" (Take the A Train) previously produced no FD at all.
   ("G3", the user's other reported case, was confirmed a one-off
   special not worth chasing -- deliberately not added.)

2. When a chord's own quality_code isn't recognized at all (not
   merely unplayable in this tuning -- genuinely never understood),
   _apply_chord_shapes() now marks the chord symbol's own XML text
   red (reusing the same <color r="255" g="0" b="4" a="255" />
   marking already used everywhere else in this project -- BO-21's
   FDs, BO-168/179's notes) and records a distinctly-shaped
   exception (measure/beat/chord_symbol/tuning_symbol/reason -- no
   melody_pitch or selected_shape, since no shape was ever
   selected). The pre-existing "no usable shape for this tuning"
   case (quality IS recognized, nothing playable here) is
   deliberately untouched -- still a silent skip, no color, no
   exception, exactly as before this BO.
"""

import sys

sys.path.insert(0, '.')

import xml.etree.ElementTree as ET

import music

from models import Harmony

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import (
    _select_chord_shape_for_harmony,
    _apply_chord_shapes
)


DOUBLE_C = get_tunings()["Double C"]  # gCGCD


def _get_chord_service():

    return ChordService(ChordLibrary())


def _build_staff_with_harmony():

    staff = ET.Element("Staff")

    measure = ET.SubElement(staff, "Measure")

    voice = ET.SubElement(measure, "voice")

    ET.SubElement(voice, "Harmony")

    return staff


def _harmony_element_of(staff):

    return staff.find(".//{*}Harmony")


def _has_color(element):

    return element.find("{*}color") is not None


# ---------------------------------------------------------
# 1 -- the new "7b5" quality itself
# ---------------------------------------------------------

def test_7b5_added_to_chord_qualities():

    assert "7b5" in music.CHORD_QUALITIES

    # G7b5: root G (pitch class 7), major 3rd (B, 11), diminished
    # 5th (Db, 1), minor 7th (F, 5) -- confirmed real via direct
    # computation before writing this assertion.
    tones = music.chord_tones(7, "7b5")

    assert sorted(tones) == sorted([7, 11, 1, 5])


def test_7b5_added_to_display_name_table():

    # BO-121/BO-167's own confirmed gap: this second table gates
    # _select_chord_shape_for_harmony()'s own earliest return
    # independently of CHORD_QUALITIES -- fixing only
    # CHORD_QUALITIES is insufficient on its own.
    assert music.quality_code_to_display_name("7b5") == "7b5"


def test_g3_deliberately_not_added():

    # The user's own confirmation: "G3" is a one-off special, not
    # a real chord type worth adding. Documents the deliberate
    # omission as a real test, not just a comment, so a future
    # session doesn't accidentally treat its absence as a bug.
    assert "3" not in music.CHORD_QUALITIES


def test_g7b5_produces_a_real_shape():

    tuning = get_tunings()["Open G"]

    service = _get_chord_service()

    harmony = Harmony(
        measure=1, root_pc=7, quality_code="7b5", symbol="G7b5"
    )

    shape, is_exception, exception_dict, quality_recognized = (
        _select_chord_shape_for_harmony(harmony, tuning, service)
    )

    assert quality_recognized is True

    assert shape is not None

    assert shape.shape != ""


# ---------------------------------------------------------
# 2 -- red-coloring and exception logging for a genuinely
#      unrecognized chord quality
# ---------------------------------------------------------

def test_unrecognized_quality_chord_symbol_marked_red():

    staff = _build_staff_with_harmony()

    # A synthetic, deliberately nonexistent quality code --
    # never added to CHORD_QUALITIES by design, standing in for
    # any genuinely unrecognized chord type.
    harmony = Harmony(
        measure=5, root_pc=0, quality_code="xyz-not-a-real-code",
        symbol="Cxyz"
    )

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], DOUBLE_C, service
    )

    assert applied == 0

    assert skipped == 1

    harmony_element = _harmony_element_of(staff)

    assert _has_color(harmony_element)

    color = harmony_element.find("{*}color")

    assert color.attrib == {
        "r": "255", "g": "0", "b": "4", "a": "255"
    }


def test_unrecognized_quality_exception_shape():

    staff = _build_staff_with_harmony()

    harmony = Harmony(
        measure=5, root_pc=0, quality_code="xyz-not-a-real-code",
        symbol="Cxyz"
    )

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], DOUBLE_C, service
    )

    assert len(exceptions) == 1

    exception = exceptions[0]

    assert exception["measure"] == 5

    assert exception["chord_symbol"] == "Cxyz"

    assert exception["tuning_symbol"] == DOUBLE_C.symbol

    assert "reason" in exception

    # Genuinely a different shape from the existing BO-21
    # exception dict -- no melody_pitch or selected_shape, since
    # neither concept applies when no shape was ever selected.
    assert "melody_pitch" not in exception

    assert "selected_shape" not in exception


def test_recognized_but_unplayable_quality_stays_untouched():

    # The pre-existing, deliberately UNCHANGED case: a quality
    # code that IS recognized (has a real CHORD_QUALITIES/
    # QUALITY_CODE_TO_DISPLAY_NAME entry), but happens to have no
    # usable shape for this specific tuning -- must stay a silent
    # skip: no color, no exception, exactly as before this BO.
    # Mocks chord_service.get_shapes() to return an empty list
    # (same pattern test_bo33_melody_position_actual_fret.py's own
    # _service_returning() already establishes) -- the cleanest,
    # least fragile way to force "recognized quality, nothing
    # playable" without hunting for a real quality/tuning
    # combination that happens to be genuinely unplayable.
    staff = _build_staff_with_harmony()

    harmony = Harmony(
        measure=5, root_pc=0, quality_code="", symbol="C"
    )

    service = _get_chord_service()

    service.get_shapes = lambda *args, **kwargs: []

    shape, is_exception, exception_dict, quality_recognized = (
        _select_chord_shape_for_harmony(harmony, DOUBLE_C, service)
    )

    assert quality_recognized is True

    assert shape is None

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], DOUBLE_C, service
    )

    assert skipped == 1

    assert exceptions == []

    harmony_element = _harmony_element_of(staff)

    assert not _has_color(harmony_element)
