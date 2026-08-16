"""
tests/test_melody_aware_chord_shape_selection.py

Regression tests for BO-20: chord-shape selection now considers
the melody note occurring at the same musical location as each
chord, preferring a voicing that contains that exact pitch --
without letting melody preference override the existing
completeness/quality ranking across categories (see this
file's own investigation notes below).

Architecture, reusing existing pieces rather than introducing a
new representation:

- chord_service.get_shapes_for_exact_melody_pitch(): re-ranks
  get_shapes()'s own output. Within each existing voicing-
  quality CATEGORY (ROOT_PRESENT / ROOTLESS_STRONG /
  ROOTLESS_WEAK -- music.classify_voicing_quality()'s own coarse
  "how musically appropriate is this voicing" measure), shapes
  containing the melody pitch move ahead of ones that don't.
  This is a stable reordering (Python's own sorted()
  guarantee), so get_shapes()'s existing ordering (quality
  score, then playability, then verified-before-generated) is
  otherwise preserved exactly within each (category, melody-
  match) group. Deliberately does NOT let melody-matching reach
  across categories -- a complete ROOT_PRESENT shape without the
  melody note still outranks an incomplete ROOTLESS shape with
  it.

- Compares EXACT pitch (MIDI value), not merely pitch class,
  per the explicit requirement -- unlike the pre-existing
  get_shapes_for_melody()/classify_melody_realization(), which
  compare pitch class for a different, pre-existing purpose
  (melody-realization diagnostics).

- chord_generator.generate_candidates() gained an optional
  melody_pitches parameter: real investigation found that the
  task's own real-world example (melody C at aDADE's 1st
  string, fret 8) requires a fret beyond FRET_CEILING (7) to
  even be GENERATED as a candidate in the first place -- no
  amount of re-ranking can select a shape that was never
  produced. When melody_pitches is given, the per-string search
  is extended, per string, to also include whichever single
  fret would produce one of those exact pitches (only when that
  pitch is itself a chord tone), even beyond FRET_CEILING.
  Everything found this way still goes through the exact same
  hand-span and playability.py acceptance checks as every other
  candidate -- this widens what's considered, it never bypasses
  practicality. None (the default) reproduces the prior search
  range exactly, for every existing caller that doesn't pass it.

- score_generator._melody_notes_at_harmony_onset(): finds the
  melody Note(s) (models.py) sharing the exact same
  (measure, beat) as a Harmony's own onset -- both already use
  the same units (quarter-note beat position within the
  measure, computed identically by parser.py). More than one
  Note can share an onset (e.g. a block chord within the melody
  itself); all of them count.

Real-world confirmation (The Christmas Song, notation-only
fixture, Double D tuning/aDADE): the first C chord's own onset
(measure 2, beat 0.0) has melody note C5 (midi 72) at that exact
location. BO-20 selects "5758" (G3 E4 G4 C5 -- a complete C
major triad that also sounds C5 exactly), not the prior non-
melody top choice. A different shape than the task's own
"8775"-style example, but the task explicitly permits that: "do
NOT hardcode 8775 as the required answer if another equally
good melody-containing voicing legitimately ranks higher."
"""

from tunings import get_tunings

from models import ChordShape

from chord_library import ChordLibrary

from chord_service import ChordService

from chord_generator import generate_candidates

from fretboard import sounding_notes

from music import ROOT_PRESENT, ROOTLESS_STRONG, ROOTLESS_WEAK

from parser import MuseScoreFile

from score_generator import (
    _melody_notes_at_harmony_onset,
    _apply_chord_shapes,
    generate_chord_diagrams_only
)

from models import Note, Harmony

import xml.etree.ElementTree as ET


DOUBLE_D = get_tunings()["Double D"]  # aDADE -- the task's own example

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

CHRISTMAS_SONG_PATH = "The Christmas Song (notation only).mscz"


def _service():

    return ChordService(ChordLibrary())


def _mock_shape(
    shape_text, category, quality_score, source="generated"
):

    shape = ChordShape(
        tuning="aDADE", root="C", quality="Major",
        shape=shape_text, source=source
    )

    shape.voicing_quality_category = category

    shape.voicing_quality_score = quality_score

    return shape


def _service_returning(fixed_shapes):

    service = _service()

    service.get_shapes = lambda *args, **kwargs: fixed_shapes

    return service


# ---------------------------------------------------------
# 1/2 -- a chord where the existing best generic shape does
# NOT contain the melody note, but another practical shape
# does -- BO selects the melody-containing one
# ---------------------------------------------------------

def test_melody_containing_shape_preferred_over_generic_top_choice():

    service = _service()

    # Without melody: confirm what the generic top choice
    # actually is, and that it does NOT contain C5 (72).
    generic_shapes = service.get_shapes(
        DOUBLE_D, "C", 0, "", "Major"
    )

    generic_top_notes = sounding_notes(
        DOUBLE_D, generic_shapes[0].shape
    )

    assert not any(n.midi == 72 for n in generic_top_notes), (
        "test setup assumption broken: the generic top choice "
        "was expected to NOT already contain C5"
    )

    # With melody C5 at this chord's onset: the top choice must
    # now contain it.
    melody_shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_D, "C", 0, "", "Major", {72}
    )

    top_notes = sounding_notes(DOUBLE_D, melody_shapes[0].shape)

    assert any(n.midi == 72 for n in top_notes), (
        f"selected shape {melody_shapes[0].shape!r} does not "
        f"contain the melody pitch C5 (72)"
    )

    # And it must still be a genuinely complete, valid C major
    # voicing -- not merely "contains the melody note."
    sounding_pcs = {n.pitch_class for n in top_notes}

    assert {0, 4, 7} <= sounding_pcs


# ---------------------------------------------------------
# 3 -- real regression: The Christmas Song / aDADE / first C
# chord
# ---------------------------------------------------------

def test_christmas_song_first_c_chord_real_regression():

    p = MuseScoreFile(CHRISTMAS_SONG_PATH)

    p.open()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.read_harmonies(staff_used)

    first_c = next(h for h in p.harmonies if h.symbol == "C")

    onset_notes = _melody_notes_at_harmony_onset(
        first_c, p.score.notes
    )

    assert len(onset_notes) == 1

    assert onset_notes[0].name == "C5"

    service = _service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_D, "C", 0, "", "Major", {onset_notes[0].midi}
    )

    selected = shapes[0]

    notes = sounding_notes(DOUBLE_D, selected.shape)

    # The important musical test, stated directly: does the
    # selected shape actually contain the melody note.
    assert any(n.midi == onset_notes[0].midi for n in notes), (
        f"selected shape {selected.shape!r} does not contain "
        f"the melody C5 occurring with this chord"
    )

    sounding_pcs = {n.pitch_class for n in notes}

    assert {0, 4, 7} <= sounding_pcs  # still a valid C major


# ---------------------------------------------------------
# 4 -- no practical shape contains the melody note: fall back
# to the existing best-shape behavior, not an invalid/
# impractical selection
# ---------------------------------------------------------

def test_falls_back_when_no_shape_contains_melody_note():

    service = _service()

    # F# (pitch class 6) is not a C major chord tone at all
    # (C major = {C, E, G} = {0, 4, 7}) -- by construction, no
    # generated candidate can ever sound it (every candidate is
    # built to cover only chord tones), so this is guaranteed to
    # exercise the "nothing contains it" fallback path, for any
    # tuning.
    f_sharp_above_middle_c = 66

    generic_shapes = service.get_shapes(
        DOUBLE_D, "C", 0, "", "Major"
    )

    melody_shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_D, "C", 0, "", "Major", {f_sharp_above_middle_c}
    )

    assert [s.shape for s in melody_shapes] == [
        s.shape for s in generic_shapes
    ], (
        "when no shape can possibly contain the melody pitch, "
        "the ranking must be identical to the non-melody-aware "
        "existing behavior"
    )


# ---------------------------------------------------------
# 5 -- a melody-containing but inferior/incomplete voicing
# must not defeat a clearly superior complete voicing
# ---------------------------------------------------------

def test_incomplete_melody_containing_shape_does_not_beat_complete_one():

    # Constructed directly (not relying on the real generator
    # happening to produce this exact combination naturally) --
    # the precise scenario this rule protects against: a
    # ROOTLESS (incomplete) shape contains the melody pitch, a
    # ROOT_PRESENT (complete) shape doesn't. The complete one
    # must still win.
    complete_no_melody = _mock_shape(
        "2350", ROOT_PRESENT, 19.5
    )

    incomplete_with_melody = _mock_shape(
        "5750", ROOTLESS_STRONG, 8.5
    )

    service = _service_returning(
        [complete_no_melody, incomplete_with_melody]
    )

    # 5750 in aDADE sounds G3 E4 G4 E4 -- G3 (55) is the pitch
    # unique to it (not present in 2350 at all), so it's the
    # right target to confirm this test actually exercises the
    # intended scenario.
    target_pitch = sounding_notes(DOUBLE_D, "5750")[0].midi  # G3

    assert not any(
        n.midi == target_pitch
        for n in sounding_notes(DOUBLE_D, "2350")
    ), (
        "test setup assumption broken: the complete shape was "
        "expected to NOT already contain the target pitch"
    )

    ranked = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_D, "C", 0, "", "Major", {target_pitch}
    )

    assert ranked[0].shape == "2350", (
        f"expected the complete ROOT_PRESENT voicing to win "
        f"despite not containing the melody pitch, got "
        f"{ranked[0].shape!r} instead -- an incomplete voicing "
        f"defeated a clearly superior one"
    )


# ---------------------------------------------------------
# 6 -- no melody note at a chord's exact onset: behavior must
# be identical to pre-BO-20
# ---------------------------------------------------------

def test_no_melody_note_at_onset_retains_prior_behavior():

    harmony = Harmony(
        measure=5, root_pc=0, quality_code="", symbol="C"
    )

    unrelated_melody_notes = [
        Note(midi=72, measure=5, beat=1.0),  # different beat
        Note(midi=64, measure=6, beat=0.0),  # different measure
    ]

    matches = _melody_notes_at_harmony_onset(
        harmony, unrelated_melody_notes
    )

    assert matches == []

    service = _service()

    generic_shapes = service.get_shapes(
        DOUBLE_D, "C", 0, "", "Major"
    )

    # get_shapes_for_exact_melody_pitch() with an empty pitch
    # set must reproduce get_shapes()'s own order exactly.
    empty_melody_shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_D, "C", 0, "", "Major", set()
    )

    assert [s.shape for s in empty_melody_shapes] == [
        s.shape for s in generic_shapes
    ]


# ---------------------------------------------------------
# 7 -- existing TAB must not influence melody-note
# determination: both a TAB-containing source and a
# notation-only source use the treble-clef melody identically
# ---------------------------------------------------------

def test_melody_notes_at_onset_ignores_which_staff_style():
    """
    _melody_notes_at_harmony_onset() itself only ever operates
    on whatever melody Note list it's given -- it has no
    awareness of TAB at all, and generate_chord_diagrams_only()
    (score_generator.py) already established, independently of
    BO-20, that melody notes always come from
    _find_notation_staff_element()'s resolved notation staff,
    never from any existing TAB (see that function's own
    docstring). This test confirms the matching logic itself
    behaves identically regardless of what the caller's source
    score originally contained -- there's nothing TAB-specific
    for it to special-case.
    """

    harmony = Harmony(
        measure=2, root_pc=0, quality_code="", symbol="C"
    )

    melody_notes = [Note(midi=72, measure=2, beat=0.0)]

    matches = _melody_notes_at_harmony_onset(
        harmony, melody_notes
    )

    assert len(matches) == 1

    assert matches[0].midi == 72


def test_full_pipeline_notation_only_uses_treble_clef_melody():

    p = MuseScoreFile(CHRISTMAS_SONG_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.read_harmonies(staff_used)

    service = _service()

    output_path, applied, skipped, exceptions = (
        generate_chord_diagrams_only(
            p, DOUBLE_D, staff_used, "output", service,
            filename="test_bo20_notation_only.mscz"
        )
    )

    try:

        assert applied > 0

        import zipfile

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

        # No new staff created -- confirms this remains a
        # notation-only-in, notation-only-out transformation,
        # matching every prior task's own requirement.
        assert len(staves) == 1

    finally:

        import os

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 8 -- BO-19 FretDiagram behavior remains correct, including
# for melody-driven shapes with a lowest fret above 4
# ---------------------------------------------------------

def test_bo19_fret_number_and_visible_frets_still_correct():

    staff = ET.Element("Staff")

    measure = ET.SubElement(staff, "Measure")

    voice = ET.SubElement(measure, "voice")

    ET.SubElement(voice, "Harmony")

    harmony = Harmony(
        measure=1, root_pc=0, quality_code="", symbol="C"
    )

    melody_notes = [Note(midi=72, measure=1, beat=0.0)]

    service = _service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], DOUBLE_D, service,
        melody_notes=melody_notes
    )

    assert applied == 1

    fret_diagram = staff.find(".//{*}FretDiagram")

    frets_element = fret_diagram.find("{*}frets")

    assert frets_element.text == "4"

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    # BO-20's own search-widening means the actual lowest fret
    # used here can vary; whatever it is, BO-19's fretOffset
    # behavior must still apply correctly to it.
    dots_absolute = {}

    fret_offset = (
        int(fret_offset_element.text)
        if fret_offset_element is not None else 0
    )

    for string_element in fret_diagram.iter():

        if string_element.tag.split("}")[-1] != "string":

            continue

        string_no = int(string_element.attrib["no"])

        dot = string_element.find("{*}dot")

        marker = string_element.find("{*}marker")

        if dot is not None:

            dots_absolute[string_no] = (
                int(dot.attrib["fret"]) + fret_offset
            )

        elif marker is not None:

            dots_absolute[string_no] = 0

    open_notes = DOUBLE_D.notes[1:]  # 4th to 1st

    sounding_midi_values = {
        open_notes[string_no] + fret
        for string_no, fret in dots_absolute.items()
    }

    assert 72 in sounding_midi_values, (
        "expected the melody pitch C5 (72) to appear among the "
        "shape's actual sounding notes, on whichever string the "
        "selected shape happens to put it -- the melody note "
        "doesn't have to land on any particular string (see "
        "score_generator.py's own module notes on this)"
    )

    lowest_fretted = min(
        v for v in dots_absolute.values() if v > 0
    )

    if lowest_fretted >= 2:

        assert fret_offset_element is not None

        assert int(fret_offset_element.text) == (
            lowest_fretted - 1
        )

    else:

        assert fret_offset_element is None
