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
    TEST_FOLDER / "scores"
    / "White Christmas (G (gCGBD)).mscz"
)

OUTPUT_FOLDER = TEST_FOLDER / "output"


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


def _get_generated_banjo_staff(root):
    """
    Locate the freshly-created TAB staff in an OUTPUT file --
    always the LAST content <Staff>, since generation now always
    appends exactly one new banjo Part+Staff, never reuses or
    modifies any pre-existing one.
    """

    score_element = root.find("{*}Score")

    content_staves = [
        c for c in score_element
        if c.tag.split("}")[-1] == "Staff"
    ]

    return content_staves[-1]


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

        # Under the current behavior, generation always builds
        # fresh from staff_used (the notation staff) -- existing
        # TAB elsewhere in the score is never used as a harmony
        # source. So harmonies read directly from staff_used
        # should match what was applied/skipped, with no
        # redirection needed.
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

        from score_generator import _find_notation_staff_element

        _, source_staff_number = _find_notation_staff_element(
            p.root, staff_used
        )

        p.read_harmonies(source_staff_number)

        # First real chord symbol with a generated diagram: its
        # written dots must match EXACTLY what
        # chord_service.get_shapes() itself returns as the top
        # shape for this tuning -- confirms the written XML is
        # really BO's own selected shape, not something else.
        #
        # IMPORTANT: must walk only the generated TAB staff's own
        # subtree (always the LAST content staff now -- see
        # _get_generated_banjo_staff()), matching exactly how
        # score_generator.py's _apply_chord_shapes() scopes it
        # internally -- White Christmas has Harmony elements on
        # THREE different staves (29/35/29), so walking
        # root.iter() directly (every staff combined) misaligns
        # harmony_index against p.harmonies and produces a false
        # mismatch. This was confirmed to be a bug in this test,
        # not in score_generator.py itself.
        output_staff_element = _get_generated_banjo_staff(root)

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


# ---------------------------------------------------------
# BO-15-FIX -- generating TAB from a notation-only source
# ---------------------------------------------------------
#
# CHRISTMAS_SONG_NOTATION_ONLY_PATH is a genuine notation-only
# MuseScore file, derived from a real score by removing its
# existing banjo Part/Staff entirely (not synthetic/fabricated
# content). No file available to this project was actually
# notation-only to begin with; this is the documented, honest
# way that gap was closed for testing.

CHRISTMAS_SONG_NOTATION_ONLY_PATH = (
    TEST_FOLDER.parent / "The Christmas Song (notation only).mscz"
)


def _load_christmas_song():

    p = MuseScoreFile(CHRISTMAS_SONG_NOTATION_ONLY_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.estimate_key()
    p.read_harmonies(staff_used)

    return p, staff_used


def test_notation_only_source_creates_tab_staff():
    """
    The exact failure this task fixes: generate_mscz() must not
    raise "No staff with TAB" for a source with no TAB staff at
    all -- it must create one.
    """

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, retuned, string_data_count, applied, skipped = (
        generate_mscz(
            p, target_tuning, staff_used, OUTPUT_FOLDER,
            filename="test_christmas_song_new_tab.mscz",
            chord_service=_get_chord_service()
        )
    )

    try:

        assert output_path.exists()

        assert retuned > 0

        assert string_data_count >= 1

        assert applied > 0

    finally:

        if output_path.exists():

            output_path.unlink()


def test_notation_only_output_is_valid_mscz_with_new_tab_part():

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, retuned, _, applied, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_valid.mscz",
        chord_service=_get_chord_service()
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            assert archive.testzip() is None

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)  # must parse cleanly

        score_element = root.find("{*}Score")

        part_track_names = [
            child.find("{*}trackName").text
            for child in score_element
            if child.tag.split("}")[-1] == "Part"
            and child.find("{*}trackName") is not None
        ]

        assert "Banjo" in part_track_names

        assert len(part_track_names) >= 2

    finally:

        if output_path.exists():

            output_path.unlink()


def test_notation_only_original_staff_preserved_untouched():

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    original_source_pitches = []

    for element in p.root.iter():

        if element.tag.split("}")[-1] != "Note":

            continue

        pitch = element.find("{*}pitch")

        if pitch is not None:

            original_source_pitches.append(pitch.text)

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_preserved.mscz",
        chord_service=_get_chord_service()
    )

    try:

        regenerated = MuseScoreFile(output_path)

        regenerated.open()
        regenerated.read_title()
        regenerated.read_time_signature()

        assert regenerated.score.title == p.score.title

        assert regenerated.time_signature == p.time_signature

        regenerated_pitches = []

        for element in regenerated.root.iter():

            if element.tag.split("}")[-1] != "Note":

                continue

            pitch = element.find("{*}pitch")

            if pitch is not None:

                regenerated_pitches.append(pitch.text)

        assert (
            regenerated_pitches[:len(original_source_pitches)]
            == original_source_pitches
        )

    finally:

        if output_path.exists():

            output_path.unlink()


def test_notation_only_tab_has_correct_tuning_and_positions():

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_tuning.mscz",
        chord_service=_get_chord_service()
    )

    try:

        regenerated = MuseScoreFile(output_path)

        regenerated.open()
        regenerated.read_time_signature()

        tab_notes = regenerated.read_tab_tuning()

        assert tab_notes == target_tuning.notes

        identified = identify_tuning(tab_notes)

        assert identified is not None

        assert identified.name == "A Modal Sawmill"

        tab_staff = _get_generated_banjo_staff(regenerated.root)

        assert tab_staff is not None

        fret_values = []

        for element in tab_staff.iter():

            if element.tag.split("}")[-1] != "Note":

                continue

            fret = element.find("{*}fret")

            if fret is not None:

                fret_values.append(int(fret.text))

        assert len(fret_values) > 0

        assert all(0 <= f <= 22 for f in fret_values)

    finally:

        if output_path.exists():

            output_path.unlink()


def test_notation_only_chord_symbols_present_in_new_tab():

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, applied, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_chords.mscz",
        chord_service=_get_chord_service()
    )

    try:

        assert applied > 0

        regenerated = MuseScoreFile(output_path)

        regenerated.open()
        regenerated.read_time_signature()

        tab_staff = _get_generated_banjo_staff(regenerated.root)

        harmony_count = sum(
            1 for el in tab_staff.iter()
            if el.tag.split("}")[-1] == "Harmony"
        )

        fret_diagram_count = sum(
            1 for el in tab_staff.iter()
            if el.tag.split("}")[-1] == "FretDiagram"
        )

        assert harmony_count > 0

        assert fret_diagram_count == applied

    finally:

        if output_path.exists():

            output_path.unlink()


# ---------------------------------------------------------
# BO-15-FIX-2 -- generated staff eid uniqueness and real
# musical duration (not merely valid XML)
# ---------------------------------------------------------
#
# Root cause found for MuseScore's "Incomplete measure: Found
# 0/1" errors on a newly created staff: <eid> values from the
# deep-copied source staff were never regenerated, so the new
# TAB staff (and its linked companion) duplicated every eid
# from the original -- confirmed by direct comparison against
# a real, known-good file, where every content staff (including
# a genuine TAB+linked-companion pair) has 100% distinct eids,
# zero shared between any two staves.

def test_generated_staff_eids_are_globally_unique():

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_eids.mscz",
        chord_service=_get_chord_service()
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        all_eids = [
            element.text for element in root.iter()
            if element.tag.split("}")[-1] == "eid"
        ]

        assert len(all_eids) > 0

        assert len(all_eids) == len(set(all_eids)), (
            f"{len(all_eids) - len(set(all_eids))} duplicate "
            "<eid> values found -- this is exactly the defect "
            "that caused MuseScore's 'Incomplete measure' errors"
        )

    finally:

        if output_path.exists():

            output_path.unlink()


def test_generated_tab_measures_match_source_duration_profile():
    """
    Confirms real musical duration was copied faithfully, not
    merely valid XML structure. Compares the new TAB staff's
    per-measure computed duration (via parser.py's own EXISTING
    _duration_value(), reused rather than duplicated) against
    the ORIGINAL source staff's own per-measure duration,
    measure for measure -- not against an absolute "every
    measure equals the time signature" check, since
    _duration_value() has a known, pre-existing limitation (no
    tuplet support, confirmed present in this real source file)
    that would misreport some of the SOURCE's own genuine
    measures too. Comparing new-vs-source neutralizes that
    limitation while still catching any real corruption
    (missing/altered Chord or Rest content) introduced by
    copying.
    """

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    from score_generator import _find_staff_element

    source_staff = _find_staff_element(p.root, staff_used)

    def _measure_durations(staff_element, duration_source):

        durations = []

        for measure in staff_element:

            if measure.tag.split("}")[-1] != "Measure":

                continue

            total = 0.0

            for voice in measure:

                if voice.tag.split("}")[-1] != "voice":

                    continue

                for child in voice:

                    tag = child.tag.split("}")[-1]

                    if tag in ("Chord", "Rest"):

                        total += duration_source._duration_value(
                            child
                        )

            durations.append(total)

        return durations

    source_durations = _measure_durations(source_staff, p)

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_duration.mscz",
        chord_service=_get_chord_service()
    )

    try:

        regenerated = MuseScoreFile(output_path)

        regenerated.open()
        regenerated.read_time_signature()

        tab_staff = _get_generated_banjo_staff(regenerated.root)

        tab_durations = _measure_durations(
            tab_staff, regenerated
        )

        assert len(tab_durations) == len(source_durations)

        assert len(tab_durations) > 0

        for measure_index, (source_total, tab_total) in enumerate(
            zip(source_durations, tab_durations)
        ):

            assert abs(source_total - tab_total) < 0.001, (
                f"measure {measure_index + 1}: source duration "
                f"{source_total} != generated TAB duration "
                f"{tab_total}"
            )

    finally:

        if output_path.exists():

            output_path.unlink()


# ---------------------------------------------------------
# BO-16 -- exactly one Banjo definition Staff, no linked
# companion (the actual root cause of the "Incomplete measure"
# errors, confirmed by direct comparison against a real
# MuseScore-created reference file)
# ---------------------------------------------------------

def test_generated_banjo_part_has_exactly_one_staff():
    """
    Confirmed by direct comparison against a real MuseScore-
    created reference file: adding a banjo instrument the
    normal way creates exactly ONE definition Staff, with no
    <linkedTo> at all. An earlier version of this code created
    a second "linked companion" staff, based on an incorrect
    generalization from files where a user had separately,
    optionally added one -- that extra staff was the actual
    cause of MuseScore reporting "Incomplete measure" on every
    generated file.
    """

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_one_staff.mscz",
        chord_service=_get_chord_service()
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        score_element = root.find("{*}Score")

        banjo_part = None

        for child in score_element:

            if child.tag.split("}")[-1] != "Part":

                continue

            track_name = child.find("{*}trackName")

            if (
                track_name is not None
                and track_name.text == "Banjo"
            ):

                banjo_part = child

                break

        assert banjo_part is not None

        def_staves = [
            c for c in banjo_part
            if c.tag.split("}")[-1] == "Staff"
        ]

        assert len(def_staves) == 1

        linked_to = def_staves[0].find("{*}linkedTo")

        assert linked_to is None

        # Correspondingly, only ONE new content Staff should
        # have been added for this part (original Piano staff
        # plus this one banjo staff, nothing more).
        content_staves = [
            c for c in score_element
            if c.tag.split("}")[-1] == "Staff"
        ]

        assert len(content_staves) == 2

    finally:

        if output_path.exists():

            output_path.unlink()


# ---------------------------------------------------------
# BO-16-2 -- new staff's first measure needs an explicit
# KeySig, and Tempo/Segment must not be duplicated from the
# source (confirmed by direct comparison against a real
# MuseScore-created reference file, where a real paste-into-
# new-staff operation produces exactly this structure)
# ---------------------------------------------------------

def test_new_tab_staff_first_measure_has_keysig():
    """
    A source staff that never states an explicit KeySig
    anywhere (relying on MuseScore's implicit default) still
    needs one added explicitly on a NEW staff's first measure --
    confirmed as the likely cause of "Incomplete measure" errors
    persisting from measure 1 onward in every previously
    generated notation-only file.
    """

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_keysig.mscz",
        chord_service=_get_chord_service()
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        score_element = root.find("{*}Score")

        content_staves = [
            c for c in score_element
            if c.tag.split("}")[-1] == "Staff"
        ]

        banjo_staff = content_staves[-1]

        first_measure = [
            m for m in banjo_staff
            if m.tag.split("}")[-1] == "Measure"
        ][0]

        voice = [
            v for v in first_measure
            if v.tag.split("}")[-1] == "voice"
        ][0]

        first_child_tag = list(voice)[0].tag.split("}")[-1]

        assert first_child_tag == "KeySig", (
            f"expected the new staff's first measure to begin "
            f"with KeySig, got {first_child_tag} first"
        )

    finally:

        if output_path.exists():

            output_path.unlink()


def test_new_tab_staff_matches_reference_structure_exactly():
    """
    The strongest available check without a live MuseScore
    instance: the generated Banjo staff's per-measure voice
    content structure (element tag sequence) must match a REAL
    MuseScore-created reference file exactly, measure for
    measure -- not merely valid XML, not merely correct
    duration sums, but the same structural shape a real paste-
    into-new-staff operation actually produces.
    """

    reference_path = (
        TEST_FOLDER.parent
        / "The_Christmas_Song__notation_and_TAB_.mscz"
    )

    if (
        not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists()
        or not reference_path.exists()
    ):

        print(
            "SKIPPED: notation-only fixture or real MuseScore "
            "reference file not found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_structure_match.mscz",
        chord_service=_get_chord_service()
    )

    try:

        def load_root(path):

            with zipfile.ZipFile(path) as archive:

                mscx_name = [
                    n for n in archive.namelist()
                    if n.endswith(".mscx")
                ][0]

                return ET.fromstring(archive.read(mscx_name))

        def get_banjo_staff(root):

            score_element = root.find("{*}Score")

            staves = [
                c for c in score_element
                if c.tag.split("}")[-1] == "Staff"
            ]

            return staves[-1]

        def voice_tag_sequence(measure):

            for voice in measure:

                if voice.tag.split("}")[-1] != "voice":

                    continue

                return [
                    child.tag.split("}")[-1] for child in voice
                ]

            return None

        reference_root = load_root(reference_path)

        generated_root = load_root(output_path)

        reference_measures = [
            m for m in get_banjo_staff(reference_root)
            if m.tag.split("}")[-1] == "Measure"
        ]

        generated_measures = [
            m for m in get_banjo_staff(generated_root)
            if m.tag.split("}")[-1] == "Measure"
        ]

        assert len(reference_measures) == len(generated_measures)

        assert len(reference_measures) > 0

        for index, (ref_measure, gen_measure) in enumerate(
            zip(reference_measures, generated_measures)
        ):

            ref_seq = voice_tag_sequence(ref_measure)

            gen_seq = voice_tag_sequence(gen_measure)

            assert ref_seq == gen_seq, (
                f"measure {index + 1}: reference structure "
                f"{ref_seq} != generated structure {gen_seq}"
            )

    finally:

        if output_path.exists():

            output_path.unlink()


def test_new_tab_staff_measures_have_only_voice_as_direct_child():
    """
    Confirmed 100% consistent across every measure in a real
    MuseScore-created reference file: a genuinely pasted-into-
    new-staff Measure has ONLY <voice> as a direct child -- no
    <eid>, <stretch>, <LayoutBreak>, or any other Measure-level
    metadata carried over from the source. This was the actual
    remaining cause of "Incomplete measure" errors persisting
    even after every WITHIN-voice fix (KeySig/Tempo/Segment) was
    already confirmed correct -- an earlier structural
    comparison checked voice content only and missed this
    entirely.
    """

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p, staff_used = _load_christmas_song()

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_christmas_song_measure_children.mscz",
        chord_service=_get_chord_service()
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        score_element = root.find("{*}Score")

        content_staves = [
            c for c in score_element
            if c.tag.split("}")[-1] == "Staff"
        ]

        banjo_staff = content_staves[-1]

        measures = [
            m for m in banjo_staff
            if m.tag.split("}")[-1] == "Measure"
        ]

        assert len(measures) > 0

        for index, measure in enumerate(measures):

            child_tags = [
                c.tag.split("}")[-1] for c in measure
            ]

            assert child_tags == ["voice"], (
                f"measure {index + 1}: expected only ['voice'] "
                f"as direct children, got {child_tags}"
            )

    finally:

        if output_path.exists():

            output_path.unlink()


# ---------------------------------------------------------
# BO-17 -- existing TAB must be ignored entirely, never used
# or modified as a shortcut, regardless of whether the input
# score happens to already contain it
# ---------------------------------------------------------

def test_existing_tab_is_ignored_and_fresh_tab_generated():
    """
    Case 2 from the explicit clarification: a source score that
    already contains TAB (White Christmas, a real example) must
    be processed identically to a genuinely notation-only score
    -- the existing TAB is neither used, modified, nor removed;
    it's simply ignored, and BO generates a brand-new banjo
    arrangement from the treble-clef notation exactly as if the
    existing TAB had never been there.
    """

    p, staff_used = _load()

    target_tuning = get_tunings()["Open G"]

    output_path, retuned, _, applied, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_existing_tab_ignored.mscz",
        chord_service=_get_chord_service()
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        with zipfile.ZipFile(WHITE_CHRISTMAS_PATH) as archive:

            original_mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            original_xml_bytes = archive.read(original_mscx_name)

        generated_root = ET.fromstring(xml_bytes)

        original_root = ET.fromstring(original_xml_bytes)

        def staff_note_fret_counts(root):

            score_element = root.find("{*}Score")

            staves = [
                c for c in score_element
                if c.tag.split("}")[-1] == "Staff"
            ]

            counts = []

            for staff in staves:

                notes = sum(
                    1 for el in staff.iter()
                    if el.tag.split("}")[-1] == "Note"
                )

                frets = sum(
                    1 for el in staff.iter()
                    if el.tag.split("}")[-1] == "fret"
                )

                counts.append((notes, frets))

            return counts

        original_counts = staff_note_fret_counts(original_root)

        generated_counts = staff_note_fret_counts(generated_root)

        # The original score's own staves (Piano + its
        # pre-existing Banjo TAB) are present UNCHANGED, in the
        # same order, with identical note/fret counts -- proving
        # the existing TAB was neither modified nor removed.
        assert generated_counts[:len(original_counts)] == (
            original_counts
        )

        # Exactly one NEW staff has been appended beyond the
        # original ones, and it's a fully-fretted fresh TAB
        # staff generated from the notation (matching Piano's
        # own note count, all fretted).
        assert len(generated_counts) == len(original_counts) + 1

        new_staff_notes, new_staff_frets = generated_counts[-1]

        assert new_staff_notes == new_staff_frets

        assert new_staff_notes == retuned

        assert applied > 0

    finally:

        if output_path.exists():

            output_path.unlink()


def test_existing_tab_tuning_never_influences_generated_tuning():
    """
    The generated staff's StringData must reflect ONLY the
    tuning BO selected -- never anything derived from the
    source's own pre-existing TAB tuning (White Christmas's
    original TAB uses a different tuning than the one requested
    here).
    """

    p, staff_used = _load()

    target_tuning = get_tunings()["C Standard"]

    output_path, _, _, _, _ = generate_mscz(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        filename="test_existing_tab_tuning_ignored.mscz",
        chord_service=_get_chord_service()
    )

    try:

        regenerated = MuseScoreFile(output_path)

        regenerated.open()

        regenerated.read_time_signature()

        tab_notes = regenerated.read_tab_tuning()

        assert tab_notes == target_tuning.notes

    finally:

        if output_path.exists():

            output_path.unlink()
