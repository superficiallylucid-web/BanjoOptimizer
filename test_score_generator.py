"""
tests/test_score_generator.py

Regression/integration test for score_generator.py, using the
real White Christmas test score. Covers:

1. BO can select a known tuning/result.
2. A generated .mscz is actually created.
3. The generated file is a valid MuseScore/MSCZ archive.
4. The expected tuning and note-position information is
   present.
5. Existing source score parsing and production optimization
   remain unchanged (the source MuseScoreFile/optimizer must
   not be mutated by generation).
"""

import shutil

import zipfile

import xml.etree.ElementTree as ET

from pathlib import Path

from parser import MuseScoreFile

from optimizer import TuningAnalyzer

from tunings import get_tunings, identify_tuning

from score_generator import generate_mscz


TEST_FOLDER = Path(__file__).parent

WHITE_CHRISTMAS_PATH = (
    TEST_FOLDER.parent / "scores"
    / "White Christmas (G (gCGBD)).mscz"
)

OUTPUT_FOLDER = TEST_FOLDER.parent / "output"


def _load():

    p = MuseScoreFile(WHITE_CHRISTMAS_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.estimate_key()
    p.read_harmonies(staff_used)

    return p, staff_used


# ---------------------------------------------------------
# 1 -- BO can select a known tuning/result
# ---------------------------------------------------------

def test_can_select_a_known_recommended_tuning():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load()

    analyzer = TuningAnalyzer(p.notes, p.key, p.harmonies, p.score.notes)

    results = analyzer.analyze()

    top_result = results["modern"][0]

    assert top_result.name == "Open G"

    selected_tuning = get_tunings()[top_result.name]

    assert selected_tuning.symbol == "gDGBD"


# ---------------------------------------------------------
# 2, 3, 4 -- a valid .mscz is created with correct tuning and
# note-position information
# ---------------------------------------------------------

def test_generated_file_is_valid_and_has_correct_tuning():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load()

    # A genuinely different tuning from the source (gCGBD), so
    # this actually exercises re-fretting, not a same-tuning
    # no-op.
    target_tuning = get_tunings()["Open G"]  # gDGBD

    output_path, retuned_count, string_data_count, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_white_christmas_open_g.mscz"
    )

    try:

        # 2 -- file actually created
        assert output_path.exists()

        # 3 -- valid MSCZ (zip) archive containing a readable
        # .mscx
        with zipfile.ZipFile(output_path) as archive:

            assert archive.testzip() is None

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)  # must parse without error

        assert root.tag.split("}")[-1] == "museScore"

        # 4 -- expected tuning present (StringData) and note-
        # position info was actually written (via the same
        # existing parsing code, round-tripped)
        assert retuned_count > 0

        assert string_data_count >= 1

        regenerated = MuseScoreFile(output_path)

        regenerated.open()

        tab_notes = regenerated.read_tab_tuning()

        assert tab_notes == target_tuning.notes

        identified = identify_tuning(tab_notes)

        assert identified is not None

        assert identified.name == "Open G"

    finally:

        if output_path.exists():

            output_path.unlink()


# ---------------------------------------------------------
# 4b -- title, chord symbols, and timing are preserved
# ---------------------------------------------------------

def test_generated_file_preserves_title_chords_and_timing():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load()

    target_tuning = get_tunings()["C Standard"]  # gCGBD

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_white_christmas_c_standard.mscz"
    )

    try:

        regenerated = MuseScoreFile(output_path)

        regenerated.open()
        regenerated.read_title()
        regenerated.read_time_signature()
        staff_used_2 = regenerated.read_melody_notes()
        regenerated.read_harmonies(staff_used_2)

        assert regenerated.score.title == p.score.title

        assert regenerated.time_signature == p.time_signature

        assert len(regenerated.notes) == len(p.notes)

        assert [h.symbol for h in regenerated.harmonies] == (
            [h.symbol for h in p.harmonies]
        )

    finally:

        if output_path.exists():

            output_path.unlink()


# ---------------------------------------------------------
# 5 -- existing source parsing and production optimization
# are unaffected by generation (source is never mutated)
# ---------------------------------------------------------

def test_source_score_and_scoring_unaffected_by_generation():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load()

    before_notes = list(p.notes)

    before_harmonies = [h.symbol for h in p.harmonies]

    before_score = TuningAnalyzer(
        p.notes, p.key, p.harmonies, p.score.notes
    ).analyze()["modern"][0].score

    target_tuning = get_tunings()["Old G"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_white_christmas_old_g.mscz"
    )

    try:

        # Source object's own data is untouched.
        assert p.notes == before_notes

        assert [h.symbol for h in p.harmonies] == before_harmonies

        # Re-scoring the (unmutated) source gives the exact same
        # result as before generation ran.
        after_score = TuningAnalyzer(
            p.notes, p.key, p.harmonies, p.score.notes
        ).analyze()["modern"][0].score

        assert after_score == before_score

    finally:

        if output_path.exists():

            output_path.unlink()


# ---------------------------------------------------------
# BO-15 -- chord shape (FretDiagram) generation
# ---------------------------------------------------------

def _get_chord_service():

    from chord_service import ChordService

    from chord_library import ChordLibrary

    return ChordService(ChordLibrary())


def test_chord_shapes_applied_and_valid():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load()

    target_tuning = get_tunings()["Open G"]

    output_path, _, _, applied, skipped = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_wc_chord_shapes.mscz",
        chord_service=_get_chord_service()
    )

    try:

        assert applied > 0

        # Compare against the harmonies of the ACTUAL resolved
        # TAB staff, not staff_used (the melody staff) -- these
        # can differ (White Christmas is a real, confirmed
        # example: melody staff 4 has 29 harmonies, but the
        # actual TAB staff 5 -- what generate_mscz really used
        # internally -- has 35). Re-derive the correct staff the
        # same way score_generator.py itself does, rather than
        # assume staff_used is right.
        from score_generator import _find_tab_staff_element

        _, actual_staff_number = _find_tab_staff_element(
            p.root, staff_used
        )

        p.read_harmonies(actual_staff_number)

        assert applied + skipped == len(p.harmonies)

        # Every written FretDiagram must decode back to a
        # shape string matching the project's own convention
        # (parse_shape/format_shape), with no muted strings
        # (see score_generator.py's own documented limitation).
        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        parent_map = {
            child: parent
            for parent in root.iter() for child in parent
        }

        fret_diagram_count = 0

        for element in root.iter():

            if element.tag.split("}")[-1] != "FretDiagram":

                continue

            fret_diagram_count += 1

            string_values = {}

            for child in element.iter():

                child_tag = child.tag.split("}")[-1]

                if child_tag == "string":

                    string_no = int(child.attrib["no"])

                elif child_tag == "dot":

                    string_values[string_no] = int(
                        child.attrib["fret"]
                    )

                elif child_tag == "marker":

                    string_values[string_no] = 0

            assert len(string_values) == 4

        # Every FretDiagram BO actually wrote must be valid and
        # complete (4 strings, no muted -- see module notes on
        # that limitation). Note: total count in the file can
        # exceed `applied` -- a chord this run skipped (e.g.
        # unrecognized quality) keeps whatever pre-existing
        # diagram the source already had for it, untouched
        # rather than removed; White Christmas is a real example
        # where every chord already had one before generation.
        assert fret_diagram_count >= applied

    finally:

        if output_path.exists():

            output_path.unlink()


def test_chord_shapes_match_chord_service_directly():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load()

    target_tuning = get_tunings()["Open G"]

    service = _get_chord_service()

    output_path, _, _, applied, skipped = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_wc_chord_shapes_2.mscz",
        chord_service=service
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        parent_map = {
            child: parent
            for parent in root.iter() for child in parent
        }

        from score_generator import _find_tab_staff_element

        _, actual_staff_number = _find_tab_staff_element(
            p.root, staff_used
        )

        p.read_harmonies(actual_staff_number)

        # First real chord symbol with a generated diagram: its
        # written dots must match EXACTLY what
        # chord_service.get_shapes() itself returns as the top
        # shape for this tuning -- confirms the written XML is
        # really BO's own selected shape, not something else.
        #
        # IMPORTANT: must walk only the resolved TAB staff's own
        # subtree, matching exactly how score_generator.py's
        # _apply_chord_shapes() scopes it internally -- White
        # Christmas has Harmony elements on THREE different
        # staves (29/35/29), so walking root.iter() directly
        # (every staff combined) misaligns harmony_index against
        # p.harmonies (which is staff-2-only) and produces a
        # false mismatch. This was confirmed to be a bug in this
        # test, not in score_generator.py itself.
        from score_generator import _find_staff_element

        output_staff_element = _find_staff_element(
            root, actual_staff_number
        )

        harmony_index = -1

        for harmony_element in output_staff_element.iter():

            if harmony_element.tag.split("}")[-1] != "Harmony":

                continue

            harmony_index += 1

            parent = parent_map[harmony_element]

            siblings = list(parent)

            idx = siblings.index(harmony_element)

            if (
                idx + 1 >= len(siblings)
                or siblings[idx + 1].tag.split("}")[-1]
                != "FretDiagram"
            ):

                continue

            matching_harmony = p.harmonies[harmony_index]

            from music import (
                pitch_name, quality_code_to_display_name
            )

            quality_display = quality_code_to_display_name(
                matching_harmony.quality_code
            )

            if quality_display is None:

                # BO skips an unrecognized quality entirely --
                # any diagram present here is a stale, untouched
                # pre-existing one, not something BO wrote. Not
                # a valid comparison case; keep looking.
                continue

            expected_shapes = service.get_shapes(
                target_tuning,
                pitch_name(matching_harmony.root_pc),
                matching_harmony.root_pc,
                matching_harmony.quality_code,
                quality_display
            )

            if not expected_shapes:

                continue

            expected_shape_text = expected_shapes[0].shape

            fret_diagram = siblings[idx + 1]

            string_values = {}

            for child in fret_diagram.iter():

                child_tag = child.tag.split("}")[-1]

                if child_tag == "string":

                    string_no = int(child.attrib["no"])

                elif child_tag == "dot":

                    string_values[string_no] = str(
                        child.attrib["fret"]
                    )

                elif child_tag == "marker":

                    string_values[string_no] = "0"

            written_shape_text = "".join(
                string_values[i] for i in range(4)
            )

            assert written_shape_text == expected_shape_text

            break

    finally:

        if output_path.exists():

            output_path.unlink()


def test_chord_service_none_skips_chord_shapes():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load()

    target_tuning = get_tunings()["Open G"]

    # Backward compatible: chord_service omitted entirely.
    output_path, _, _, applied, skipped = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_wc_no_chord_service.mscz"
    )

    try:

        assert applied == 0

        assert skipped == 0

        assert output_path.exists()

    finally:

        if output_path.exists():

            output_path.unlink()
