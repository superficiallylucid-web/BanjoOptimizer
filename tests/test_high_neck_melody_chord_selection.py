"""
tests/test_high_neck_melody_chord_selection.py

Regression tests for BO-21-FOLLOWUP: BO-20's melody-aware
chord-shape selection previously couldn't discover or select a
high-neck shape even when it was genuinely the correct,
practical answer.

Root cause (see chord_generator.py's own module notes and
fretboard.py's own module notes on the shape-string format):
two separate, compounding limitations, both confirmed by direct
investigation before any code changed --

1. The shape-string format itself (parse_shape()/format_shape())
   could only represent a single-digit fret (0-9) per string,
   with no delimiter. A fret of 10 or higher (e.g. 12) could not
   be encoded at all -- format_shape([0,10,10,12]) previously
   produced the corrupted, ambiguous string "0101012". Fixed by
   wrapping multi-digit frets in parentheses (e.g. "(12)"),
   matching the existing precedent set by the "--" mute-token
   convention -- fully backward compatible, every existing
   single-digit shape parses identically to before.

2. BO-20's melody-pitch search-widening (added to reach a
   melody note beyond the normal fret ceiling) only widened the
   ONE string that exactly matched the melody pitch, not the
   other strings. A melody note needing a high fret on one
   string often means the WHOLE shape needs to sit up the neck
   to stay practical -- pairing a high fret on one string with
   only normal low-position options everywhere else produces a
   huge hand span that never survives the existing filter,
   regardless of how far that one string's own search reaches.
   Fixed: chord_generator.generate_candidates() now widens every
   string's search to the full practical neck (up to 22 frets)
   for chord-tone-producing frets whenever the melody pitch is
   genuinely a chord tone -- letting the EXISTING hand-span and
   playability.py filters do the actual practicality filtering
   from this wider pool, exactly as they always have. When the
   melody pitch isn't a chord tone at all, nothing is widened
   (no shape could ever contain it regardless), preserving
   get_shapes()'s own non-melody-aware ranking exactly.

Real-world confirmation (The Christmas Song, notation-only
fixture, A Modal Sawmill tuning/aEADE): the score's FINAL chord
(measure 32, beat 3.0, symbol "C") has melody note E5 (midi 76)
at that exact onset -- confirmed to equal aEADE's 1st string
open + fret 12 exactly. BO-20 now selects "0(10)(10)(12)"
(E3-G4-C5-E5, a complete C major triad, hand_span=2) instead of
the prior top choice "0350", which doesn't contain E5 at all.
"""

import zipfile

import os

import xml.etree.ElementTree as ET

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from chord_generator import generate_candidates, hand_span

from fretboard import sounding_notes, parse_shape, format_shape

from playability import evaluate as evaluate_playability

from parser import MuseScoreFile

from score_generator import (
    _apply_chord_shapes,
    _melody_notes_at_harmony_onset,
    generate_chord_diagrams_only
)

from models import Note, Harmony


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

DOUBLE_D = get_tunings()["Double D"]  # aDADE -- BO-20's own case

CHRISTMAS_SONG_PATH = "The Christmas Song (notation only).mscz"


def _get_chord_service():

    return ChordService(ChordLibrary())


# ---------------------------------------------------------
# 1 -- the final Christmas Song chord identifies the correct
# exact melody pitch
# ---------------------------------------------------------

def test_final_chord_identifies_correct_melody_pitch():

    p = MuseScoreFile(CHRISTMAS_SONG_PATH)

    p.open()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.read_harmonies(staff_used)

    last_harmony = p.harmonies[-1]

    assert last_harmony.symbol == "C"

    onset_notes = _melody_notes_at_harmony_onset(
        last_harmony, p.score.notes
    )

    assert len(onset_notes) == 1

    assert onset_notes[0].name == "E5"

    assert onset_notes[0].midi == 76

    # Confirmed to equal aEADE's 1st string open + fret 12.
    open_1st = A_MODAL_SAWMILL.notes[4]

    assert open_1st + 12 == 76


# ---------------------------------------------------------
# 2 -- the required high-neck candidate can be generated when
# necessary to reach the melody pitch
# ---------------------------------------------------------

def test_high_neck_candidate_is_generated_when_needed():

    candidates = generate_candidates(
        tuning=A_MODAL_SAWMILL, root="C", root_pc=0,
        quality_code="", quality_display="Major",
        max_candidates=100, melody_pitches={76}
    )

    shape_texts = [c.shape for c in candidates]

    assert "0(10)(10)(12)" in shape_texts, (
        f"expected the high-neck candidate to be generated, "
        f"got: {shape_texts}"
    )

    # And it must not appear at all when no melody target is
    # given -- confirms this is genuinely additive, not a
    # change to the normal search range.
    candidates_no_melody = generate_candidates(
        tuning=A_MODAL_SAWMILL, root="C", root_pc=0,
        quality_code="", quality_display="Major",
        max_candidates=100
    )

    assert "0(10)(10)(12)" not in [
        c.shape for c in candidates_no_melody
    ]


# ---------------------------------------------------------
# 3 -- 0,10,10,12 is considered a practical candidate
# ---------------------------------------------------------

def test_shape_is_practical():

    values = [0, 10, 10, 12]

    shape_text = format_shape(values)

    assert shape_text == "0(10)(10)(12)"

    assert parse_shape(shape_text) == values

    assert hand_span(values) == 2

    result = evaluate_playability(shape_text)

    assert result.accepted, (
        f"expected this shape to be accepted as practical, "
        f"got: {result.reason}"
    )


# ---------------------------------------------------------
# 4 -- the melody-aware ranking can select a high-neck
# melody-containing candidate when appropriate
# ---------------------------------------------------------

def test_melody_aware_ranking_selects_high_neck_candidate():

    service = _get_chord_service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "", "Major", {76}
    )

    assert shapes[0].shape == "0(10)(10)(12)"


# ---------------------------------------------------------
# 5/6 -- the final chord selects 0,10,10,12, and it contains
# the exact melody pitch
# ---------------------------------------------------------

def test_final_chord_selects_expected_shape_containing_melody():

    p = MuseScoreFile(CHRISTMAS_SONG_PATH)

    p.open()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.read_harmonies(staff_used)

    last_harmony = p.harmonies[-1]

    onset_notes = _melody_notes_at_harmony_onset(
        last_harmony, p.score.notes
    )

    service = _get_chord_service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "", "Major",
        {n.midi for n in onset_notes}
    )

    selected = shapes[0]

    assert selected.shape == "0(10)(10)(12)"

    notes = sounding_notes(A_MODAL_SAWMILL, selected.shape)

    assert any(n.midi == 76 for n in notes)

    sounding_pcs = {n.pitch_class for n in notes}

    assert {0, 4, 7} <= sounding_pcs  # still a valid C major


# ---------------------------------------------------------
# 7/8 -- the resulting FretDiagram accurately represents
# 0,10,10,12, and BO-19's fretOffset/Visible Frets behavior
# is correct for it
# ---------------------------------------------------------

def test_fretdiagram_represents_shape_with_correct_bo19_encoding():

    staff = ET.Element("Staff")

    measure = ET.SubElement(staff, "Measure")

    voice = ET.SubElement(measure, "voice")

    ET.SubElement(voice, "Harmony")

    harmony = Harmony(
        measure=32, beat=3.0, root_pc=0, quality_code="",
        symbol="C"
    )

    melody_notes = [Note(midi=76, measure=32, beat=3.0)]

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], A_MODAL_SAWMILL, service,
        melody_notes=melody_notes
    )

    assert applied == 1

    fret_diagram = staff.find(".//{*}FretDiagram")

    frets_element = fret_diagram.find("{*}frets")

    assert frets_element.text == "4"

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    assert fret_offset_element is not None

    # lowest non-zero fret is 10 -> fretOffset = 10 - 1 = 9
    assert fret_offset_element.text == "9"

    open_notes = A_MODAL_SAWMILL.notes[1:]

    absolute_values = {}

    for string_element in fret_diagram.iter():

        if string_element.tag.split("}")[-1] != "string":

            continue

        string_no = int(string_element.attrib["no"])

        dot = string_element.find("{*}dot")

        marker = string_element.find("{*}marker")

        if dot is not None:

            absolute_values[string_no] = (
                int(dot.attrib["fret"]) + 9
            )

        elif marker is not None:

            absolute_values[string_no] = 0

    assert absolute_values == {0: 0, 1: 10, 2: 10, 3: 12}

    sounding_midi = {
        open_notes[i] + fret
        for i, fret in absolute_values.items()
    }

    assert 76 in sounding_midi

    # This is NOT an exception -- a practical melody-containing
    # shape was found.
    assert exceptions == []

    assert fret_diagram.find("{*}color") is None


# ---------------------------------------------------------
# 9 -- the diagram is NOT marked red by BO-21
# ---------------------------------------------------------

def test_final_chord_diagram_not_marked_red():

    p = MuseScoreFile(CHRISTMAS_SONG_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.read_harmonies(staff_used)

    service = _get_chord_service()

    output_path, applied, skipped, exceptions = (
        generate_chord_diagrams_only(
            p, A_MODAL_SAWMILL, staff_used, "output", service,
            filename="test_bo21followup_not_red.mscz"
        )
    )

    try:

        last_exception_measures = {
            e["measure"] for e in exceptions
        }

        assert 32 not in last_exception_measures, (
            "the final chord must not be reported as a "
            "melody/chord exception"
        )

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        score_element = root.find("{*}Score")

        staves = [
            c for c in score_element
            if c.tag.split("}")[-1] == "Staff"
        ]

        piano = staves[0]

        # Last FretDiagram in document order is the final
        # chord's own.
        fret_diagrams = [
            el for el in piano.iter()
            if el.tag.split("}")[-1] == "FretDiagram"
        ]

        last_fret_diagram = fret_diagrams[-1]

        assert last_fret_diagram.find("{*}color") is None

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 10 -- existing BO-20 behavior for lower-position melody-
# aware chords remains unchanged
# ---------------------------------------------------------

def test_lower_position_melody_aware_behavior_unchanged():
    """
    The Christmas Song's own first C chord (BO-20's original
    real regression example, measure 2/aDADE) must still select
    a shape that genuinely contains the melody pitch C5, and
    still be a complete, valid C major voicing -- this task's
    change to the search-widening logic must not disturb an
    already-working lower-position case.
    """

    p = MuseScoreFile(CHRISTMAS_SONG_PATH)

    p.open()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.read_harmonies(staff_used)

    first_c = next(h for h in p.harmonies if h.symbol == "C")

    onset_notes = _melody_notes_at_harmony_onset(
        first_c, p.score.notes
    )

    assert onset_notes[0].name == "C5"

    service = _get_chord_service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_D, "C", 0, "", "Major",
        {n.midi for n in onset_notes}
    )

    notes = sounding_notes(DOUBLE_D, shapes[0].shape)

    assert any(n.midi == 72 for n in notes)

    sounding_pcs = {n.pitch_class for n in notes}

    assert {0, 4, 7} <= sounding_pcs


def test_non_chord_tone_melody_still_falls_back_identically():
    """
    A melody pitch that isn't a chord tone at all must still
    produce a ranking identical to the non-melody-aware
    baseline -- confirms this task's wider search only ever
    activates when the melody pitch is genuinely reachable in
    principle, never unconditionally.
    """

    service = _get_chord_service()

    generic = service.get_shapes(
        A_MODAL_SAWMILL, "C", 0, "", "Major"
    )

    # F# (66) is not a C major chord tone.
    melody_aware = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "", "Major", {66}
    )

    assert [s.shape for s in generic] == [
        s.shape for s in melody_aware
    ]
