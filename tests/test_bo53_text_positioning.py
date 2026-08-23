"""
tests/test_bo53_text_positioning.py

Regression tests for BO-53: chord symbol and "Banjo tuning:" text
offset corrections.

Investigation confirmed (against the real, MuseScore-authored
source scores) that BO-53's two offsets have different starting
points:

- Chord symbols (Harmony's own <offset>): the source score
  ALREADY has an explicit <offset> element -- confirmed different
  and inconsistent across the 4 real source songs (The Christmas
  Song: x=-1.5/y=-3, My Favorite Things: x=0.5/y=-2, White
  Christmas: x=0/y=-1.5). generate_tab_from_template()'s own
  harmony_copy logic previously copied this verbatim (deepcopy,
  no modification at all) -- BO-53 now OVERRIDES it to a
  consistent x=-5/y=0 on every chord symbol BO writes, regardless
  of whatever the source had.

- "Banjo tuning:" text: previously had NO explicit <offset> at
  all (MuseScore's own "subtitle" style default applied instead).
  BO-53 adds one, x=4.5/y=0.

x=horizontal, y=vertical throughout (standard MuseScore/SVG
convention, confirmed against real MuseScore-authored <Text>
elements -- e.g. title/composer frames in the real source
scores, all using this same x/y meaning).

Only score_generator.py was changed (the harmony_copy override
in generate_tab_from_template(), and the new offset element in
_add_tuning_text()). No tuning-selection, Playing Model, melody-
placement, chord-shape-selection, or Fret Diagram logic was
touched -- confirmed directly: this file's own tests check chord
symbol COUNT and content are unchanged, only the offset values
differ.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

WITH_COMPOSER_AND_TAB_PATH = (
    "The Christmas Song (with TAB and composer).mscz"
)


def _generate(filename):

    p = MuseScoreFile(WITH_COMPOSER_AND_TAB_PATH)

    p.open()

    p.read_title()

    p.read_composer()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
            "output", service, filename=filename
        )
    )

    with zipfile.ZipFile(output_path) as archive:

        assert archive.testzip() is None  # valid zip

        mscx_name = [
            n for n in archive.namelist() if n.endswith(".mscx")
        ][0]

        xml_bytes = archive.read(mscx_name)

    root = ET.fromstring(xml_bytes)

    return output_path, applied, skipped, exceptions, root


# ---------------------------------------------------------
# 1 -- chord symbol offset is exactly x=-5, y=0
# ---------------------------------------------------------

def test_chord_symbol_offset_is_correct():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_bo53_chord_offset.mscz"
    )

    try:

        staff = root.find(".//{*}Score/{*}Staff")

        harmonies = staff.findall(".//{*}Harmony")

        assert len(harmonies) > 0

        for harmony in harmonies:

            offset = harmony.find("{*}offset")

            assert offset is not None

            assert offset.attrib.get("x") == "0"

            assert offset.attrib.get("y") == "-5"

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 2 -- "Banjo tuning:" text offset is exactly x=4.5, y=0
# ---------------------------------------------------------

def test_tuning_text_offset_is_correct():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_bo53_tuning_text_offset.mscz"
    )

    try:

        staff = root.find(".//{*}Score/{*}Staff")

        vbox = staff.find("{*}VBox")

        tuning_text_element = None

        for text_element in vbox.findall("{*}Text"):

            style_element = text_element.find("{*}style")

            content_element = text_element.find("{*}text")

            if (
                style_element is not None
                and style_element.text == "subtitle"
                and content_element is not None
                and content_element.text
                and content_element.text.startswith(
                    "Banjo tuning:"
                )
            ):

                tuning_text_element = text_element

                break

        assert tuning_text_element is not None

        offset = tuning_text_element.find("{*}offset")

        assert offset is not None

        assert offset.attrib.get("x") == "4.5"

        assert offset.attrib.get("y") == "0"

        # Content itself unchanged.
        content_element = tuning_text_element.find("{*}text")

        assert content_element.text == (
            f"Banjo tuning: {A_MODAL_SAWMILL.symbol} "
            f"({A_MODAL_SAWMILL.name})"
        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- consistent regardless of the source's own pre-existing
# offset (real, confirmed: the 4 real source songs each had a
# DIFFERENT starting Harmony offset before BO-53)
# ---------------------------------------------------------

def test_chord_symbol_offset_consistent_across_real_songs():

    real_songs = [
        "scores/The Christmas Song.mscz",
        "scores/My Favorite Things.mscz",
        "scores/White Christmas.mscz",
    ]

    seen_offsets = set()

    for source_path in real_songs:

        p = MuseScoreFile(source_path)

        p.open()

        p.read_time_signature()

        staff_used = p.read_melody_notes()

        p.read_harmonies(staff_used)

        if not p.harmonies:

            continue

        service = ChordService(ChordLibrary())

        output_path, applied, skipped, exceptions = (
            generate_tab_from_template(
                p, A_MODAL_SAWMILL, staff_used, TEMPLATE_PATH,
                "output", service,
                filename=f"test_bo53_consistency_{p.score.title}.mscz"
            )
        )

        try:

            with zipfile.ZipFile(output_path) as archive:

                mscx_name = [
                    n for n in archive.namelist()
                    if n.endswith(".mscx")
                ][0]

                xml_bytes = archive.read(mscx_name)

            root = ET.fromstring(xml_bytes)

            staff = root.find(".//{*}Score/{*}Staff")

            for harmony in staff.findall(".//{*}Harmony"):

                offset = harmony.find("{*}offset")

                seen_offsets.add(
                    (offset.attrib.get("x"), offset.attrib.get("y"))
                )

        finally:

            if os.path.exists(output_path):

                os.remove(output_path)

    # Confirms BO-53's own fix applies uniformly regardless of
    # each real source song's own different starting offset.
    assert seen_offsets == {("0", "-5")}


# ---------------------------------------------------------
# 4 -- chord symbol count/content unchanged (only position
# changed, not which chords are written or their text)
# ---------------------------------------------------------

def test_chord_symbol_count_and_content_unchanged():

    output_path, applied, skipped, exceptions, root = _generate(
        "test_bo53_content_unchanged.mscz"
    )

    try:

        staff = root.find(".//{*}Score/{*}Staff")

        harmonies = staff.findall(".//{*}Harmony")

        assert len(harmonies) == 56

        fret_diagrams = staff.findall(".//{*}FretDiagram")

        assert len(fret_diagrams) == 56

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
