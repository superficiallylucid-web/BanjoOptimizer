"""
tests/test_melody_chord_exceptions.py

Regression tests for BO-21: when BO-20's exact-melody-pitch
chord-shape selection can't find a practical shape containing
the melody note at a chord's own onset, the normal best
fallback shape is still used (never altered to "solve" the
exception), its FretDiagram is marked red, and one exception
entry is recorded.

XML mechanism, confirmed by direct inspection of the supplied
real MuseScore example (a manually-colored FretDiagram), not
guessed:

    <color r="255" g="0" b="4" a="255" />

...is a direct child of <FretDiagram> itself (colors the whole
diagram at once, not individual strings/dots), positioned after
<eid> and before the inner <fretDiagram>. A normal diagram
simply omits this element entirely -- confirmed against every
FretDiagram this project generated before BO-21, none of which
ever had a <color> child.

Detection logic (score_generator._apply_chord_shapes): an
exception is when a melody note existed at a chord's exact
onset (melody_pitches was non-empty) but the shape BO-20 chose
doesn't contain any of those exact pitches among its own
sounding notes -- checked directly with
fretboard.sounding_notes(), never inferred from ranking
internals. This runs strictly AFTER BO-20's own selection
completes; the exception mechanism never changes which shape
gets chosen, only how it's displayed and reported.
"""

import xml.etree.ElementTree as ET

import zipfile

import os

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from fretboard import sounding_notes, parse_shape, format_shape

from models import Note, Harmony

from parser import MuseScoreFile

from score_generator import (
    _apply_chord_shapes,
    _set_fret_diagram_content,
    generate_chord_diagrams_only
)


DOUBLE_D = get_tunings()["Double D"]  # aDADE

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

CHRISTMAS_SONG_PATH = "The Christmas Song (notation only).mscz"


def _get_chord_service():

    return ChordService(ChordLibrary())


def _build_staff_with_harmony():

    staff = ET.Element("Staff")

    measure = ET.SubElement(staff, "Measure")

    voice = ET.SubElement(measure, "voice")

    ET.SubElement(voice, "Harmony")

    return staff


def _fret_diagram_of(staff):

    return staff.find(".//{*}FretDiagram")


def _has_color(fret_diagram):

    return fret_diagram.find("{*}color") is not None


def _decode_absolute_shape(fret_diagram):

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    fret_offset = (
        int(fret_offset_element.text)
        if fret_offset_element is not None else 0
    )

    values = {}

    for string_element in fret_diagram.iter():

        if string_element.tag.split("}")[-1] != "string":

            continue

        string_no = int(string_element.attrib["no"])

        dot = string_element.find("{*}dot")

        marker = string_element.find("{*}marker")

        if dot is not None:

            values[string_no] = (
                int(dot.attrib["fret"]) + fret_offset
            )

        elif marker is not None:

            values[string_no] = 0

    return format_shape([values[i] for i in range(4)])


# ---------------------------------------------------------
# 1 -- normal chord where BO-20 finds a melody-containing
# shape: normal color, no exception
# ---------------------------------------------------------

def test_normal_melody_containing_chord_no_exception():

    staff = _build_staff_with_harmony()

    harmony = Harmony(
        measure=2, root_pc=0, quality_code="", symbol="C"
    )

    # C5 (72) IS achievable by a complete C major voicing in
    # aDADE (see BO-20's own real regression) -- this is
    # deliberately the "success" case.
    melody_notes = [Note(midi=72, measure=2, beat=0.0)]

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], DOUBLE_D, service,
        melody_notes=melody_notes
    )

    assert applied == 1

    assert exceptions == []

    fret_diagram = _fret_diagram_of(staff)

    assert not _has_color(fret_diagram)

    notes = sounding_notes(
        DOUBLE_D, _decode_absolute_shape(fret_diagram)
    )

    assert any(n.midi == 72 for n in notes)


# ---------------------------------------------------------
# 2 -- no practical melody-containing shape: fallback
# selected, diagram red, exactly one exception
# ---------------------------------------------------------

def test_no_practical_melody_shape_produces_one_exception():

    staff = _build_staff_with_harmony()

    harmony = Harmony(
        measure=2, root_pc=0, quality_code="", symbol="C"
    )

    # F# (pitch class 6) is not a C major chord tone at all
    # (C major = {C, E, G} = {0, 4, 7}) -- by construction, no
    # candidate voicing can ever sound it regardless of how far
    # the search reaches, so this is guaranteed to remain a
    # genuine exception (unlike the Cmaj7/B4 case this test used
    # before BO-21-FOLLOWUP -- that combination turned out to
    # have a genuine practical solution once candidate
    # generation was correctly widened, which is a real
    # improvement, not something to keep pretending is
    # unsolvable).
    melody_notes = [Note(midi=66, measure=2, beat=0.0)]

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], A_MODAL_SAWMILL, service,
        melody_notes=melody_notes
    )

    assert applied == 1

    assert len(exceptions) == 1

    exception = exceptions[0]

    assert exception["measure"] == 2

    assert exception["chord_symbol"] == "C"

    assert exception["melody_pitch"] == "F#4"

    assert exception["tuning_symbol"] == "aEADE"

    fret_diagram = _fret_diagram_of(staff)

    assert _has_color(fret_diagram)

    assert fret_diagram.find("{*}color").attrib == {
        "r": "255", "g": "0", "b": "4", "a": "255"
    }

    # The fallback shape must still be the genuine best choice
    # BO-20 would select without melody awareness at all, not
    # something altered to try to "fix" the exception.
    non_melody_shapes = service.get_shapes(
        A_MODAL_SAWMILL, "C", 0, "", "Major"
    )

    assert exception["selected_shape"] == non_melody_shapes[0].shape


# ---------------------------------------------------------
# 3 -- multiple exceptions in one score: every one reported,
# only those FretDiagrams red
# ---------------------------------------------------------

def test_multiple_exceptions_all_reported_only_those_red():

    staff = ET.Element("Staff")

    harmonies = []

    melody_notes = []

    # Two C/F# exceptions (F# is not a chord tone of C major at
    # all, so genuinely unsolvable regardless of search range),
    # one normal C/C5 success, in three separate measures.
    specs = [
        (1, 0, "", "C", 66),   # exception (F#4)
        (2, 0, "", "C", 72),   # normal (C5)
        (3, 0, "", "C", 66),   # exception (F#4)
    ]

    for measure_number, beat, quality_code, symbol, midi in specs:

        measure = ET.SubElement(staff, "Measure")

        voice = ET.SubElement(measure, "voice")

        ET.SubElement(voice, "Harmony")

        harmonies.append(
            Harmony(
                measure=measure_number, root_pc=0,
                quality_code=quality_code, symbol=symbol
            )
        )

        melody_notes.append(
            Note(midi=midi, measure=measure_number, beat=beat)
        )

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, harmonies, A_MODAL_SAWMILL, service,
        melody_notes=melody_notes
    )

    assert applied == 3

    assert len(exceptions) == 2

    assert {e["measure"] for e in exceptions} == {1, 3}

    fret_diagrams = [
        el for el in staff.iter()
        if el.tag.split("}")[-1] == "FretDiagram"
    ]

    assert len(fret_diagrams) == 3

    red_flags = [_has_color(fd) for fd in fret_diagrams]

    assert red_flags == [True, False, True]


# ---------------------------------------------------------
# 4 -- a chord with no melody note at its exact onset: no
# exception, normal diagram
# ---------------------------------------------------------

def test_no_melody_note_at_onset_no_exception():

    staff = _build_staff_with_harmony()

    harmony = Harmony(
        measure=5, root_pc=0, quality_code="maj7", symbol="Cmaj7"
    )

    # Melody notes exist, but none at THIS chord's onset.
    melody_notes = [Note(midi=71, measure=9, beat=0.0)]

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], A_MODAL_SAWMILL, service,
        melody_notes=melody_notes
    )

    assert applied == 1

    assert exceptions == []

    fret_diagram = _fret_diagram_of(staff)

    assert not _has_color(fret_diagram)


# ---------------------------------------------------------
# 5 -- the red diagram still contains exactly the selected
# chord shape
# ---------------------------------------------------------

def test_red_diagram_contains_exact_selected_shape():

    staff = _build_staff_with_harmony()

    harmony = Harmony(
        measure=2, root_pc=0, quality_code="", symbol="C"
    )

    melody_notes = [Note(midi=66, measure=2, beat=0.0)]

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], A_MODAL_SAWMILL, service,
        melody_notes=melody_notes
    )

    fret_diagram = _fret_diagram_of(staff)

    written_shape = _decode_absolute_shape(fret_diagram)

    assert written_shape == exceptions[0]["selected_shape"]


# ---------------------------------------------------------
# 6 -- BO-19 fretOffset behavior still works on a red diagram
# ---------------------------------------------------------

def test_bo19_fret_offset_still_correct_on_red_diagram():

    fret_diagram = ET.Element("FretDiagram")

    values = parse_shape("0350")  # lowest fretted = 3

    wrote = _set_fret_diagram_content(
        fret_diagram, values, is_exception=True
    )

    assert wrote

    assert _has_color(fret_diagram)

    frets_element = fret_diagram.find("{*}frets")

    assert frets_element.text == "4"

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    assert fret_offset_element is not None

    assert fret_offset_element.text == "2"  # lowest(3) - 1

    assert _decode_absolute_shape(fret_diagram) == "0350"


# ---------------------------------------------------------
# 7 -- existing TAB must not influence exception detection --
# both notation-only and TAB-containing sources use the same
# treble-clef melody, identically
# ---------------------------------------------------------

def test_exception_detection_independent_of_tab_presence():
    """
    _apply_chord_shapes() only ever operates on whatever
    melody_notes list it's given -- it has no awareness of TAB
    at all, and generate_chord_diagrams_only() already
    guarantees (independently of BO-21, established in BO-17/
    BO-20) that melody_notes always comes from the resolved
    NOTATION staff, never any existing TAB. Confirms the
    exception logic itself produces the identical result
    regardless of what the source score's structure looked
    like -- there's nothing TAB-specific for it to special-case.
    """

    def run_with(melody_notes):

        staff = _build_staff_with_harmony()

        harmony = Harmony(
            measure=2, root_pc=0, quality_code="",
            symbol="C"
        )

        service = _get_chord_service()

        return _apply_chord_shapes(
            staff, [harmony], A_MODAL_SAWMILL, service,
            melody_notes=melody_notes
        )

    # Same melody data, however it was originally sourced.
    melody_notes = [Note(midi=66, measure=2, beat=0.0)]

    applied_a, skipped_a, exceptions_a = run_with(melody_notes)

    applied_b, skipped_b, exceptions_b = run_with(
        list(melody_notes)
    )

    assert applied_a == applied_b

    assert len(exceptions_a) == len(exceptions_b) == 1

    assert (
        exceptions_a[0]["selected_shape"]
        == exceptions_b[0]["selected_shape"]
    )


def test_full_pipeline_notation_only_produces_correct_exceptions():

    p = MuseScoreFile(CHRISTMAS_SONG_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.read_harmonies(staff_used)

    service = _get_chord_service()

    # C Standard (gCGBD) -- confirmed directly to still have a
    # genuine exception in this real fixture after BO-21-
    # FOLLOWUP's search-widening fix (the tunings this test used
    # before -- aEADE among them -- had every one of their
    # exceptions genuinely SOLVED by that fix, a real
    # improvement, not something to keep pretending is
    # unsolvable).
    c_standard = get_tunings()["C Standard"]

    output_path, applied, skipped, exceptions = (
        generate_chord_diagrams_only(
            p, c_standard, staff_used, "output", service,
            filename="test_bo21_notation_only.mscz"
        )
    )

    try:

        assert applied > 0

        assert len(exceptions) > 0

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        red_count = sum(
            1 for el in root.iter()
            if el.tag.split("}")[-1] == "FretDiagram"
            and el.find("{*}color") is not None
        )

        assert red_count == len(exceptions)

        # No new staff created -- still a notation-only-in,
        # notation-only-out transformation (BO-18 Plan B
        # architecture untouched).
        score_element = root.find("{*}Score")

        staves = [
            c for c in score_element
            if c.tag.split("}")[-1] == "Staff"
        ]

        assert len(staves) == 1

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 8 -- the original source score is not modified
# ---------------------------------------------------------

def test_original_source_score_not_modified():

    p = MuseScoreFile(CHRISTMAS_SONG_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.read_harmonies(staff_used)

    before_harmony_symbols = [h.symbol for h in p.harmonies]

    before_note_count = len(p.score.notes)

    original_color_count = sum(
        1 for el in p.root.iter()
        if el.tag.split("}")[-1] == "color"
    )

    service = _get_chord_service()

    # C Standard (gCGBD) -- still has a genuine exception in
    # this real fixture after BO-21-FOLLOWUP's fix (see
    # test_full_pipeline_notation_only_produces_correct_exceptions's
    # own comment for why aEADE no longer does).
    c_standard = get_tunings()["C Standard"]

    output_path, applied, skipped, exceptions = (
        generate_chord_diagrams_only(
            p, c_standard, staff_used, "output", service,
            filename="test_bo21_source_unmodified.mscz"
        )
    )

    try:

        assert len(exceptions) > 0

        # The caller's own already-parsed source object is
        # untouched.
        assert [h.symbol for h in p.harmonies] == (
            before_harmony_symbols
        )

        assert len(p.score.notes) == before_note_count

        assert sum(
            1 for el in p.root.iter()
            if el.tag.split("}")[-1] == "color"
        ) == original_color_count

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
