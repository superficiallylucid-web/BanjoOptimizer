"""
tests/test_chord_diagrams_only.py

Regression/integration tests for score_generator.py's
generate_chord_diagrams_only() -- BO-19, "Plan B": adds banjo
chord shape diagrams above the existing chord symbols on the
score's own notation staff, without creating a TAB staff and
without touching melody notes/frets/strings/pitches or any
existing TAB elsewhere in the score.

Covers:
1. A generated .mscz is actually created, and is a valid
   MuseScore/MSCZ archive.
2. Chord diagrams (FretDiagram) are added to the notation
   staff, using the same chord_service machinery generate_mscz()
   already uses -- no second, independent chord-selection
   system.
3. Melody notes are byte-for-byte unchanged (no fret/string
   added, no pitch changed).
4. Any pre-existing TAB staff is left completely untouched --
   not modified, not removed, not used as a source.
5. No new Part or Staff is created at all.
6. The tuning is visibly present, both in the filename (as its
   actual notation, e.g. "gDGBD", not only its name) and as
   text inside the generated score itself.
7. Title, lyrics, and existing formatting remain intact.
"""

import zipfile

import xml.etree.ElementTree as ET

from pathlib import Path

from parser import MuseScoreFile

from tunings import get_tunings

from score_generator import generate_chord_diagrams_only


TEST_FOLDER = Path(__file__).parent.parent

WHITE_CHRISTMAS_PATH = (
    TEST_FOLDER / "scores"
    / "White Christmas (G (gCGBD)).mscz"
)

CHRISTMAS_SONG_NOTATION_ONLY_PATH = (
    TEST_FOLDER / "The Christmas Song (notation only).mscz"
)

OUTPUT_FOLDER = TEST_FOLDER / "output"


def _get_chord_service():

    from chord_service import ChordService

    from chord_library import ChordLibrary

    return ChordService(ChordLibrary())


def _load_white_christmas():

    p = MuseScoreFile(WHITE_CHRISTMAS_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.estimate_key()
    p.read_harmonies(staff_used)

    return p, staff_used


def _get_notation_staff(root):
    """
    White Christmas's own notation (Piano) staff is always the
    FIRST content staff -- confirmed real structure (Piano
    declared before Banjo).
    """

    score_element = root.find("{*}Score")

    staves = [
        c for c in score_element
        if c.tag.split("}")[-1] == "Staff"
    ]

    return staves[0]


def test_chord_diagrams_applied_and_valid_file():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load_white_christmas()

    target_tuning = get_tunings()["Open G"]

    output_path, applied, skipped, _exceptions = generate_chord_diagrams_only(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        _get_chord_service(),
        filename="test_chord_diagrams_valid.mscz"
    )

    try:

        assert output_path.exists()

        assert applied > 0

        with zipfile.ZipFile(output_path) as archive:

            assert archive.testzip() is None

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)  # must parse cleanly

        assert root.tag.split("}")[-1] == "museScore"

        notation_staff = _get_notation_staff(root)

        fret_diagram_count = sum(
            1 for el in notation_staff.iter()
            if el.tag.split("}")[-1] == "FretDiagram"
        )

        assert fret_diagram_count == applied

    finally:

        if output_path.exists():

            output_path.unlink()


def test_melody_completely_unchanged():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load_white_christmas()

    original_notation_staff = _get_notation_staff(p.root)

    original_pitches = []

    for element in original_notation_staff.iter():

        if element.tag.split("}")[-1] != "Note":

            continue

        pitch = element.find("{*}pitch")

        if pitch is not None:

            original_pitches.append(pitch.text)

    target_tuning = get_tunings()["Open G"]

    output_path, _, _, _exceptions = generate_chord_diagrams_only(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        _get_chord_service(),
        filename="test_melody_unchanged.mscz"
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        notation_staff = _get_notation_staff(root)

        generated_pitches = []

        fret_count = 0

        for element in notation_staff.iter():

            if element.tag.split("}")[-1] == "Note":

                pitch = element.find("{*}pitch")

                if pitch is not None:

                    generated_pitches.append(pitch.text)

            if element.tag.split("}")[-1] == "fret":

                fret_count += 1

        # Same pitches, same order -- nothing added, removed,
        # or reordered.
        assert generated_pitches == original_pitches

        # No fret/string was ever added to the notation staff --
        # this function must never touch melody position data.
        assert fret_count == 0

    finally:

        if output_path.exists():

            output_path.unlink()


def test_existing_tab_completely_untouched():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load_white_christmas()

    def staff_note_fret_fd_counts(root):

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

            fret_diagrams = sum(
                1 for el in staff.iter()
                if el.tag.split("}")[-1] == "FretDiagram"
            )

            counts.append((notes, frets, fret_diagrams))

        return counts

    with zipfile.ZipFile(WHITE_CHRISTMAS_PATH) as archive:

        original_mscx_name = [
            n for n in archive.namelist()
            if n.endswith(".mscx")
        ][0]

        original_xml_bytes = archive.read(original_mscx_name)

    original_root = ET.fromstring(original_xml_bytes)

    original_counts = staff_note_fret_fd_counts(original_root)

    target_tuning = get_tunings()["Open G"]

    output_path, applied, _, _exceptions = generate_chord_diagrams_only(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        _get_chord_service(),
        filename="test_existing_tab_untouched.mscz"
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        generated_root = ET.fromstring(xml_bytes)

        generated_counts = staff_note_fret_fd_counts(
            generated_root
        )

        # No new staff created -- same total staff count.
        assert len(generated_counts) == len(original_counts)

        # Staff 0 (notation) gained FretDiagrams but kept its
        # note/fret counts unchanged.
        assert (
            generated_counts[0][0], generated_counts[0][1]
        ) == (original_counts[0][0], original_counts[0][1])

        assert generated_counts[0][2] == applied

        # Every OTHER staff (the pre-existing TAB and its
        # linked companion) is byte-for-byte identical --
        # completely untouched.
        assert generated_counts[1:] == original_counts[1:]

    finally:

        if output_path.exists():

            output_path.unlink()


def test_no_new_part_or_staff_created():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load_white_christmas()

    with zipfile.ZipFile(WHITE_CHRISTMAS_PATH) as archive:

        original_mscx_name = [
            n for n in archive.namelist()
            if n.endswith(".mscx")
        ][0]

        original_xml_bytes = archive.read(original_mscx_name)

    original_root = ET.fromstring(original_xml_bytes)

    original_score_element = original_root.find("{*}Score")

    original_part_count = sum(
        1 for c in original_score_element
        if c.tag.split("}")[-1] == "Part"
    )

    target_tuning = get_tunings()["Open G"]

    output_path, _, _, _exceptions = generate_chord_diagrams_only(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        _get_chord_service(),
        filename="test_no_new_part.mscz"
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        generated_root = ET.fromstring(xml_bytes)

        generated_score_element = generated_root.find(
            "{*}Score"
        )

        generated_part_count = sum(
            1 for c in generated_score_element
            if c.tag.split("}")[-1] == "Part"
        )

        assert generated_part_count == original_part_count

    finally:

        if output_path.exists():

            output_path.unlink()


def test_tuning_visible_in_filename_and_score_text():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load_white_christmas()

    target_tuning = get_tunings()["Open G"]

    output_path, _, _, _exceptions = generate_chord_diagrams_only(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        _get_chord_service()
    )

    try:

        # Filename must include the actual tuning NOTATION
        # (symbol), not only its name -- a name alone is
        # explicitly not sufficient.
        assert target_tuning.symbol in output_path.name

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        all_text_content = [
            el.text for el in root.iter()
            if el.tag.split("}")[-1] == "text" and el.text
        ]

        assert any(
            target_tuning.symbol in text
            for text in all_text_content
        )

    finally:

        if output_path.exists():

            output_path.unlink()


def test_title_and_harmonies_preserved_via_parser():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load_white_christmas()

    before_harmony_symbols = [h.symbol for h in p.harmonies]

    target_tuning = get_tunings()["Open G"]

    output_path, applied, skipped, _exceptions = generate_chord_diagrams_only(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        _get_chord_service(),
        filename="test_title_harmonies_preserved.mscz"
    )

    try:

        regenerated = MuseScoreFile(output_path)

        regenerated.open()
        regenerated.read_title()
        regenerated.read_time_signature()

        new_staff_used = regenerated.read_melody_notes()

        regenerated.read_harmonies(new_staff_used)

        assert regenerated.score.title == p.score.title

        assert [
            h.symbol for h in regenerated.harmonies
        ] == before_harmony_symbols

        assert applied + skipped == len(before_harmony_symbols)

    finally:

        if output_path.exists():

            output_path.unlink()


def test_chord_diagram_shape_matches_chord_service_directly():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p, staff_used = _load_white_christmas()

    target_tuning = get_tunings()["Open G"]

    service = _get_chord_service()

    output_path, _, _, _exceptions = generate_chord_diagrams_only(
        p, target_tuning, staff_used, OUTPUT_FOLDER, service,
        filename="test_shape_matches_service.mscz"
    )

    try:

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        notation_staff = _get_notation_staff(root)

        parent_map = {
            child: parent
            for parent in notation_staff.iter()
            for child in parent
        }

        from music import (
            pitch_name, quality_code_to_display_name
        )

        harmony_index = -1

        for harmony_element in notation_staff.iter():

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

            quality_display = quality_code_to_display_name(
                matching_harmony.quality_code
            )

            if quality_display is None:

                continue

            # This function's own real chord-shape selection is
            # melody-aware (generate_chord_diagrams_only() passes
            # melody_notes through to _apply_chord_shapes(),
            # confirmed directly) -- the plain, melody-blind
            # service.get_shapes()[0] this test previously
            # compared against predates that and was never
            # updated, since this test was silently skipped by a
            # pre-existing path bug (fixed separately) for an
            # unknown period and never actually ran until now.
            # BO-54 -- the real writer also now passes next_
            # harmony (HP continuity); matched here too, or this
            # comparison would be checking against a stale,
            # next_harmony-less selection that no longer matches
            # what's actually written.
            from score_generator import (
                _select_chord_shape_for_harmony
            )

            next_harmony = (
                p.harmonies[harmony_index + 1]
                if harmony_index + 1 < len(p.harmonies) else None
            )

            selected_shape, _, _ = (
                _select_chord_shape_for_harmony(
                    matching_harmony, target_tuning, service,
                    melody_notes=p.score.notes,
                    next_harmony=next_harmony
                )
            )

            if selected_shape is None:

                continue

            expected_shape_text = selected_shape.shape

            fret_diagram = siblings[idx + 1]

            fret_offset_element = fret_diagram.find(
                "{*}fretOffset"
            )

            fret_offset = (
                int(fret_offset_element.text)
                if fret_offset_element is not None else 0
            )

            string_values = {}

            for child in fret_diagram.iter():

                child_tag = child.tag.split("}")[-1]

                if child_tag == "string":

                    string_no = int(child.attrib["no"])

                elif child_tag == "dot":

                    string_values[string_no] = str(
                        int(child.attrib["fret"]) + fret_offset
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


def test_notation_only_source_also_works():
    """
    Case 1 (no existing TAB at all) must work identically to
    Case 2 (existing TAB, ignored) -- same as generate_mscz()'s
    own equivalent requirement.
    """

    if not CHRISTMAS_SONG_NOTATION_ONLY_PATH.exists():

        print(
            "SKIPPED: notation-only Christmas Song fixture not "
            "found locally"
        )

        return

    p = MuseScoreFile(CHRISTMAS_SONG_NOTATION_ONLY_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.estimate_key()
    p.read_harmonies(staff_used)

    target_tuning = get_tunings()["A Modal Sawmill"]

    output_path, applied, skipped, _exceptions = generate_chord_diagrams_only(
        p, target_tuning, staff_used, OUTPUT_FOLDER,
        _get_chord_service(),
        filename="test_notation_only_chord_diagrams.mscz"
    )

    try:

        assert output_path.exists()

        assert applied > 0

        with zipfile.ZipFile(output_path) as archive:

            assert archive.testzip() is None

    finally:

        if output_path.exists():

            output_path.unlink()
