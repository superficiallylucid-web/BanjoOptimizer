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

    output_path, retuned_count, string_data_count = generate_mscz(
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

    output_path, _, _ = generate_mscz(
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

    output_path, _, _ = generate_mscz(
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
