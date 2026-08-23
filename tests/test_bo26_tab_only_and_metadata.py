"""
tests/test_bo26_tab_only_and_metadata.py

Regression tests for BO-26: TAB-only output (already established
by BO-23, confirmed here rather than re-implemented) plus
carrying over the source score's own Title and Composer/arranger
(Project Properties) and the existing "Banjo tuning: ..." text
onto the generated TAB score.

Two real, derived fixtures used here (both built by injecting a
real Composer/arranger value into an otherwise-genuine source
file -- never fabricating melody/chord/TAB content itself):

- "The Christmas Song (with composer).mscz": derived from the
  project's own notation-only fixture, no pre-existing TAB.
- "The Christmas Song (with TAB and composer).mscz": derived
  from the project's own real, MuseScore-authored notation+TAB
  reference file -- confirms generation still works, and still
  ignores the source's own pre-existing TAB (per BO-17), when
  the input itself already contains TAB.

Does not touch chord generation, FD generation, fretboard-
diagram XML encoding, tuning logic, or the BO-21 exception
system -- this task is scoped to output structure and metadata
only.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile, DURATIONS

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

WITH_COMPOSER_NO_TAB_PATH = (
    "The Christmas Song (with composer).mscz"
)

WITH_COMPOSER_AND_TAB_PATH = (
    "The Christmas Song (with TAB and composer).mscz"
)

EXPECTED_COMPOSER = "Mel Torme / Bob Wells"

EXPECTED_TITLE = "The Christmas Song"


def _tuplet_aware_measure_duration(measure_element):

    total = 0.0

    tuplet_scale = 1.0

    for voice in measure_element.findall("{*}voice"):

        for el in voice:

            tag = el.tag.split("}")[-1]

            if tag == "Tuplet":

                normal_notes_element = el.find(
                    "{*}normalNotes"
                )

                actual_notes_element = el.find(
                    "{*}actualNotes"
                )

                if (
                    normal_notes_element is not None
                    and actual_notes_element is not None
                ):

                    tuplet_scale = (
                        int(normal_notes_element.text)
                        / int(actual_notes_element.text)
                    )

            elif tag == "endTuplet":

                tuplet_scale = 1.0

            elif tag in ("Chord", "Rest"):

                duration_type_element = el.find(
                    "{*}durationType"
                )

                dots_element = el.find("{*}dots")

                base = DURATIONS.get(
                    duration_type_element.text, 0.0
                )

                dots = (
                    int(dots_element.text)
                    if dots_element is not None else 0
                )

                value = base

                add = base / 2

                for _ in range(dots):

                    value += add

                    add /= 2

                total += value * tuplet_scale

    return total


def _generate(source_path, filename):

    p = MuseScoreFile(source_path)

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

    root = ET.fromstring(xml_bytes)  # must parse cleanly

    return output_path, applied, skipped, exceptions, root


def _vbox_text_by_style(vbox, style_name):

    for text_element in vbox.findall("{*}Text"):

        style_element = text_element.find("{*}style")

        if (
            style_element is not None
            and style_element.text == style_name
        ):

            content_element = text_element.find("{*}text")

            font_element = content_element.find("{*}font")

            return (
                font_element.tail if font_element is not None
                else content_element.text
            )

    return None


# ---------------------------------------------------------
# 1 -- output contains TAB and no treble-clef staff
# ---------------------------------------------------------

def test_output_is_tab_only():

    output_path, applied, skipped, exceptions, root = _generate(
        WITH_COMPOSER_AND_TAB_PATH,
        "test_bo26_tab_only.mscz"
    )

    try:

        score_el = root.find(".//{*}Score")

        staves = [
            c for c in score_el
            if c.tag.split("}")[-1] == "Staff"
        ]

        assert len(staves) == 1

        part_el = root.find(".//{*}Part")

        staff_defs = part_el.findall("{*}Staff")

        assert len(staff_defs) == 1

        # The one remaining staff genuinely contains TAB content
        # (fret/string on its Notes), not just a bare notation
        # staff.
        first_note = staves[0].find(".//{*}Note")

        assert first_note.find("{*}fret") is not None

        assert first_note.find("{*}string") is not None

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 2 -- Title exactly matches the input
# ---------------------------------------------------------

def test_title_exactly_matches_input():

    output_path, applied, skipped, exceptions, root = _generate(
        WITH_COMPOSER_AND_TAB_PATH,
        "test_bo26_title.mscz"
    )

    try:

        score_el = root.find(".//{*}Score")

        work_title_tag = score_el.find(
            './/{*}metaTag[@name="workTitle"]'
        )

        assert work_title_tag.text == EXPECTED_TITLE

        staff = score_el.find("{*}Staff")

        vbox = staff.find("{*}VBox")

        assert (
            _vbox_text_by_style(vbox, "title")
            == EXPECTED_TITLE
        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- Composer/arranger exactly matches the input
# ---------------------------------------------------------

def test_composer_exactly_matches_input():

    output_path, applied, skipped, exceptions, root = _generate(
        WITH_COMPOSER_AND_TAB_PATH,
        "test_bo26_composer.mscz"
    )

    try:

        score_el = root.find(".//{*}Score")

        composer_tag = score_el.find(
            './/{*}metaTag[@name="composer"]'
        )

        assert composer_tag.text == EXPECTED_COMPOSER

        staff = score_el.find("{*}Staff")

        vbox = staff.find("{*}VBox")

        assert (
            _vbox_text_by_style(vbox, "composer")
            == EXPECTED_COMPOSER
        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4 -- no composer in source: left absent, not a misleading
# placeholder
# ---------------------------------------------------------

def test_no_composer_in_source_left_absent():

    output_path, applied, skipped, exceptions, root = _generate(
        "The Christmas Song (notation only).mscz",
        "test_bo26_no_composer.mscz"
    )

    try:

        score_el = root.find(".//{*}Score")

        composer_tag = score_el.find(
            './/{*}metaTag[@name="composer"]'
        )

        assert composer_tag is None or not composer_tag.text

        staff = score_el.find("{*}Staff")

        vbox = staff.find("{*}VBox")

        assert _vbox_text_by_style(vbox, "composer") is None

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 5 -- tuning description appears on the TAB score, using the
# actual target tuning (not hardcoded)
# ---------------------------------------------------------

def test_tuning_description_present_and_correct():

    output_path, applied, skipped, exceptions, root = _generate(
        WITH_COMPOSER_AND_TAB_PATH,
        "test_bo26_tuning_text.mscz"
    )

    try:

        score_el = root.find(".//{*}Score")

        staff = score_el.find("{*}Staff")

        vbox = staff.find("{*}VBox")

        subtitle_text = _vbox_text_by_style(vbox, "subtitle")

        assert subtitle_text == (
            f"Banjo tuning: {A_MODAL_SAWMILL.symbol} "
            f"({A_MODAL_SAWMILL.name})"
        )

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 6/7 -- chord symbols and FretDiagrams remain present
# ---------------------------------------------------------

def test_chord_symbols_and_fretdiagrams_present():

    output_path, applied, skipped, exceptions, root = _generate(
        WITH_COMPOSER_AND_TAB_PATH,
        "test_bo26_chords_fds.mscz"
    )

    try:

        staff = root.find(".//{*}Score/{*}Staff")

        harmonies = staff.findall(".//{*}Harmony")

        fret_diagrams = staff.findall(".//{*}FretDiagram")

        assert len(harmonies) == 56

        assert len(fret_diagrams) == 56

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 8 -- BO-20 through BO-25 behavior unchanged: the same
# confirmed real values from earlier sessions still appear
# ---------------------------------------------------------

def test_bo20_through_bo25_behavior_unchanged():

    output_path, applied, skipped, exceptions, root = _generate(
        WITH_COMPOSER_AND_TAB_PATH,
        "test_bo26_prior_behavior.mscz"
    )

    try:

        staff = root.find(".//{*}Score/{*}Staff")

        measures = staff.findall("{*}Measure")

        # Measure 1: BO-24's approach-the-chord fix.
        m1_voice = list(measures[0].find("{*}voice"))

        note = m1_voice[4].find("{*}Note")  # after KeySig/TimeSig/Rest/Rest

        assert note.find("{*}fret").text == "8"

        assert note.find("{*}string").text == "3"

        # Measure 2: Cmaj7 -- full history: BO-22-FOLLOWUP
        # confirmed "7" (complete C-E-G-B voicing, 0(10)98).
        # BO-54's first pass changed this to "6" (0798, missing
        # the 5th) as a following-melody-only HP-continuity side
        # effect. The BO-54 REVISION restored "7": the algorithm
        # now also weighs the incoming hand position (the C chord
        # immediately before Cmaj7, 0(10)(10)0) -- 0(10)98 shares
        # a real fretted anchor with it (3rd string, fret 10);
        # 0798 shares none. The user's own direct musical
        # judgment confirmed this is correct: the following
        # melody's own low-position destination doesn't actually
        # depend on staying near Cmaj7's own HP at all (reachable
        # via an open/5th-string bridge either way), so the
        # incoming-position anchor is what genuinely matters here.
        m2_voice = list(measures[1].find("{*}voice"))

        cmaj7_fd = m2_voice[4]

        assert cmaj7_fd.find("{*}fretOffset").text == "7"

        cmaj7_onset_note = m2_voice[5].find("{*}Note")

        assert cmaj7_onset_note.find("{*}fret").text == "9"

        assert cmaj7_onset_note.find("{*}string").text == "1"

        # Measure 2: Em onset note (BO-24's "1-0" fix).
        em_onset_note = m2_voice[11].find("{*}Note")

        assert em_onset_note.find("{*}fret").text == "0"

        assert em_onset_note.find("{*}string").text == "0"

        # No exceptions for this passage (BO-21 unchanged).
        assert exceptions == []

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 9 -- every measure sums correctly and the file opens
# cleanly (structural integrity, unrelated to metadata)
# ---------------------------------------------------------

def test_output_structurally_valid():

    output_path, applied, skipped, exceptions, root = _generate(
        WITH_COMPOSER_AND_TAB_PATH,
        "test_bo26_structural.mscz"
    )

    try:

        staff = root.find(".//{*}Score/{*}Staff")

        measures = staff.findall("{*}Measure")

        assert len(measures) == 34

        bad_measures = [
            (i + 1, _tuplet_aware_measure_duration(m))
            for i, m in enumerate(measures)
            if abs(_tuplet_aware_measure_duration(m) - 4.0)
            > 1e-9
        ]

        assert bad_measures == []

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 10 -- also works with an input that has NO pre-existing TAB
# (the notation-only fixture), and still generates TAB-only
# output correctly
# ---------------------------------------------------------

def test_works_with_input_that_has_no_tab():

    output_path, applied, skipped, exceptions, root = _generate(
        "The Christmas Song (notation only).mscz",
        "test_bo26_no_tab_source.mscz"
    )

    try:

        score_el = root.find(".//{*}Score")

        staves = [
            c for c in score_el
            if c.tag.split("}")[-1] == "Staff"
        ]

        assert len(staves) == 1

        first_note = staves[0].find(".//{*}Note")

        assert first_note.find("{*}fret") is not None

        work_title_tag = score_el.find(
            './/{*}metaTag[@name="workTitle"]'
        )

        assert work_title_tag.text == EXPECTED_TITLE

        assert applied == 56

        assert skipped == 0

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
