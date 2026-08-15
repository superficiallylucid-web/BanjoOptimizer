"""
tests/test_chord_fingering_correctness.py

Regression tests for BO-18: the chord shapes chord_service.py
selects (and score_generator.py writes into FretDiagram XML)
must actually be musically valid voicings of the requested
chord -- every generated diagram must contain every one of the
chord's own defining tones, not just the root or an easy-to-
play but incomplete subset.

Root cause (see chord_generator.py's own comment on
ranking_key): candidates were ranked by an additive score
(playability + voicing quality). _score_candidate()'s open-
string bonus (+10 per open string, uncapped) could completely
overwhelm classify_voicing_quality()'s much smaller spread
(~4-8 points for a typical chord), letting an incomplete
voicing (missing a chord tone entirely) outrank a complete one.
Fixed with a lexicographic ranking key (quality first,
playability only as a tie-breaker among equal-quality
voicings).

Covers the specific reported cases (C and Em in aEADE), plus a
direct trace of the full pipeline: chord symbol -> chord_service
result -> MuseScore FretDiagram XML -- confirming the fret
values actually written correspond to the selected shape after
MuseScore's own string-order convention (confirmed real,
directly against known-good MuseScore data, NOT from memory:
FretDiagram's <string no="N"> matches this project's own
internal convention directly, unlike Note's <string>, which is
reversed -- see score_generator.py's own module notes).
"""

import xml.etree.ElementTree as ET

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from fretboard import sounding_notes, parse_shape

from music import chord_tones

from models import Harmony

from score_generator import _apply_chord_shapes


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]


def _get_chord_service():

    return ChordService(ChordLibrary())


def _assert_shape_contains_all_chord_tones(
    tuning, shape_text, root_pc, quality_code, label
):

    notes = sounding_notes(tuning, shape_text)

    sounding_pitch_classes = {note.pitch_class for note in notes}

    required_tones = set(chord_tones(root_pc, quality_code))

    missing = required_tones - sounding_pitch_classes

    assert not missing, (
        f"{label}: shape {shape_text!r} is missing chord "
        f"tone(s) {missing} -- sounds {sorted(sounding_pitch_classes)}, "
        f"chord requires {sorted(required_tones)}"
    )


# ---------------------------------------------------------
# 1 -- the two specifically reported cases
# ---------------------------------------------------------

def test_c_major_in_aeade_top_shape_is_complete():
    """
    The exact reported case: C major in aEADE previously
    selected "0320" (sounds E, C, E, E -- missing the 5th, G,
    entirely). The top-ranked shape must now contain C, E, and
    G.
    """

    service = _get_chord_service()

    shapes = service.get_shapes(
        A_MODAL_SAWMILL, "C", 0, "", "Major"
    )

    assert shapes, "no shapes returned for C major in aEADE"

    top_shape = shapes[0]

    _assert_shape_contains_all_chord_tones(
        A_MODAL_SAWMILL, top_shape.shape, 0, "", "C major"
    )

    # The specific previously-buggy shape must not be the top
    # choice anymore (it may still legitimately appear further
    # down the list as a valid, lower-quality alternative).
    assert top_shape.shape != "0320"


def test_em_in_aeade_top_shape_is_complete():
    """
    The exact reported case: Em in aEADE previously selected
    "0220" (sounds E, B, E, E -- missing the minor 3rd, G,
    entirely -- an E5 power chord, not a proper Em voicing). The
    top-ranked shape must now contain E, G, and B.
    """

    service = _get_chord_service()

    shapes = service.get_shapes(
        A_MODAL_SAWMILL, "E", 4, "m", "Minor"
    )

    assert shapes, "no shapes returned for E minor in aEADE"

    top_shape = shapes[0]

    _assert_shape_contains_all_chord_tones(
        A_MODAL_SAWMILL, top_shape.shape, 4, "m", "E minor"
    )

    assert top_shape.shape != "0220"


# ---------------------------------------------------------
# 2 -- broader sweep: every triad/7th-chord root, in aEADE,
# must have a complete top-ranked shape -- confirms this is a
# general fix, not something that happens to work only for the
# two specifically reported chords
# ---------------------------------------------------------

def test_all_common_qualities_get_complete_top_shape_in_aeade():
    """
    Triads (major/minor -- 3 tones) always have room to cover
    every chord tone on a 4-string melody surface, so those
    require full coverage, matching the two specifically
    reported cases.

    Richer chords (7ths -- 4 tones) don't always have that room:
    confirmed directly for Cmaj7 in aEADE that NONE of the 10
    generated candidates cover all 4 tones (root_pc=0 -- see
    this test file's own investigation) -- a genuine physical
    limitation of a 4-string surface for a 4-tone chord in this
    tuning, not something a ranking fix can or should force.
    For those, the real requirement this task is actually about
    is that the TOP choice is genuinely the most complete
    option available -- covers at least as many distinct chord
    tones as the best candidate anywhere in the full pool, never
    fewer. That's the general property a ranking bug (this
    task's actual subject) could violate; "does a fully-covering
    voicing exist at all" is a separate question this task isn't
    about.
    """

    from music import pitch_name

    from chord_generator import generate_candidates

    triad_qualities = [("", "Major"), ("m", "Minor")]

    seventh_qualities = [
        ("7", "Dom 7"), ("maj7", "Maj 7"), ("m7", "min 7")
    ]

    service = _get_chord_service()

    checked = 0

    for root_pc in range(12):

        root_name = pitch_name(root_pc)

        for quality_code, quality_display in triad_qualities:

            shapes = service.get_shapes(
                A_MODAL_SAWMILL, root_name, root_pc,
                quality_code, quality_display
            )

            if not shapes:

                continue

            checked += 1

            _assert_shape_contains_all_chord_tones(
                A_MODAL_SAWMILL, shapes[0].shape, root_pc,
                quality_code,
                f"{root_name}{quality_display} (root_pc="
                f"{root_pc})"
            )

        for quality_code, quality_display in seventh_qualities:

            shapes = service.get_shapes(
                A_MODAL_SAWMILL, root_name, root_pc,
                quality_code, quality_display
            )

            if not shapes:

                continue

            checked += 1

            all_candidates = generate_candidates(
                tuning=A_MODAL_SAWMILL, root=root_name,
                root_pc=root_pc, quality_code=quality_code,
                quality_display=quality_display,
                max_candidates=100
            )

            required_tones = set(
                chord_tones(root_pc, quality_code)
            )

            def _coverage_count(shape_text):

                notes = sounding_notes(
                    A_MODAL_SAWMILL, shape_text
                )

                sounding = {n.pitch_class for n in notes}

                return len(required_tones & sounding)

            best_achievable = max(
                _coverage_count(candidate.shape)
                for candidate in all_candidates
            )

            top_coverage = _coverage_count(shapes[0].shape)

            assert top_coverage == best_achievable, (
                f"{root_name}{quality_display} (root_pc="
                f"{root_pc}): top-ranked shape "
                f"{shapes[0].shape!r} covers "
                f"{top_coverage}/{len(required_tones)} chord "
                f"tones, but {best_achievable} were achievable "
                f"among the full candidate pool -- a more "
                f"complete voicing exists and should have been "
                f"ranked first"
            )

    # Sanity check that this swept a meaningful number of real
    # cases, not zero (which would make the loop above
    # vacuously pass).
    assert checked >= 40


# ---------------------------------------------------------
# 3 -- full pipeline trace: chord symbol -> chord_service
# result -> MuseScore FretDiagram XML, confirming the fret
# values actually written match the selected shape after
# MuseScore's own string-order convention (verified directly
# against real MuseScore data during BO-15/16 -- FretDiagram's
# <string no="N"> is NOT reversed, unlike Note's <string>)
# ---------------------------------------------------------

def _build_synthetic_staff_with_harmony(root_pc, quality_code):
    """
    A minimal, synthetic content <Staff> with a single
    <Measure><voice><Harmony/></voice></Measure> -- just enough
    structure for _apply_chord_shapes() to operate on directly,
    without needing a real .mscz file.
    """

    staff = ET.Element("Staff")

    measure = ET.SubElement(staff, "Measure")

    voice = ET.SubElement(measure, "voice")

    ET.SubElement(voice, "Harmony")

    return staff


def test_fretdiagram_fret_values_match_selected_shape():
    """
    Traces the full pipeline end to end for C major in aEADE:
    obtains chord_service's own top-ranked shape, runs it
    through score_generator._apply_chord_shapes() (the exact
    function that writes FretDiagram XML in real generated
    scores), then decodes the WRITTEN XML back into a shape
    string and confirms it matches exactly -- and that the
    resulting sounding notes are a complete C major voicing.
    """

    service = _get_chord_service()

    root_pc, quality_code, quality_display = 0, "", "Major"

    expected_shapes = service.get_shapes(
        A_MODAL_SAWMILL, "C", root_pc, quality_code,
        quality_display
    )

    expected_shape_text = expected_shapes[0].shape

    staff = _build_synthetic_staff_with_harmony(
        root_pc, quality_code
    )

    harmony = Harmony(
        measure=1, root_pc=root_pc, quality_code=quality_code,
        symbol="C"
    )

    applied, skipped = _apply_chord_shapes(
        staff, [harmony], A_MODAL_SAWMILL, service
    )

    assert applied == 1

    assert skipped == 0

    fret_diagram = staff.find(".//{*}FretDiagram")

    assert fret_diagram is not None

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    fret_offset = (
        int(fret_offset_element.text)
        if fret_offset_element is not None else 0
    )

    written_values = {}

    for element in fret_diagram.iter():

        tag = element.tag.split("}")[-1]

        if tag == "string":

            string_no = int(element.attrib["no"])

        elif tag == "dot":

            # BO-19: dot fret values are RELATIVE to fretOffset
            # when it's set -- add it back to get the absolute
            # fret, matching what was actually selected.
            written_values[string_no] = int(
                element.attrib["fret"]
            ) + fret_offset

        elif tag == "marker":

            written_values[string_no] = 0

    written_shape_text = "".join(
        str(written_values[i]) for i in range(4)
    )

    assert written_shape_text == expected_shape_text, (
        f"FretDiagram XML decoded back to {written_shape_text!r}, "
        f"but chord_service selected {expected_shape_text!r} -- "
        f"the write step is transforming the shape incorrectly"
    )

    # And, independently of matching chord_service's own output,
    # confirm the WRITTEN shape is itself a musically complete
    # C major voicing -- the actual, ultimate requirement.
    _assert_shape_contains_all_chord_tones(
        A_MODAL_SAWMILL, written_shape_text, root_pc,
        quality_code, "written FretDiagram (C major)"
    )


def test_fretdiagram_string_numbering_matches_project_convention():
    """
    Directly confirms FretDiagram's own <string no="N"> uses
    this project's internal convention (N=0 is the 4th string,
    N=3 the 1st), NOT the reversed convention Note's <string>
    uses -- verified here against a known shape's expected
    per-string fret values, rather than assumed from memory.
    """

    service = _get_chord_service()

    shapes = service.get_shapes(
        A_MODAL_SAWMILL, "C", 0, "", "Major"
    )

    shape_text = shapes[0].shape

    expected_values = parse_shape(shape_text)

    staff = _build_synthetic_staff_with_harmony(0, "")

    harmony = Harmony(
        measure=1, root_pc=0, quality_code="", symbol="C"
    )

    _apply_chord_shapes(staff, [harmony], A_MODAL_SAWMILL, service)

    fret_diagram = staff.find(".//{*}FretDiagram")

    fret_offset_element = fret_diagram.find("{*}fretOffset")

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

            # BO-19: dot fret values are RELATIVE to fretOffset.
            written_fret = int(dot.attrib["fret"]) + fret_offset

        elif marker is not None:

            written_fret = 0

        else:

            written_fret = None

        assert written_fret == expected_values[string_no], (
            f"string no={string_no}: XML has fret "
            f"{written_fret}, but parse_shape({shape_text!r}) "
            f"expects {expected_values[string_no]} at that "
            f"same index -- string numbering convention "
            f"mismatch"
        )
