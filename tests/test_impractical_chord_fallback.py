"""
tests/test_impractical_chord_fallback.py

Regression tests for BO-18 FOLLOW-UP: BO must not be forced to
choose a technically-complete-but-impractical voicing when a
chord has no complete, comfortable voicing available -- and
when it falls back to a simplified (tone-omitting) voicing, it
should prefer keeping the root and defining chord-quality tones
over the non-defining perfect 5th.

Investigation summary (see chord_generator.py's own module
notes and music.py's classify_voicing_quality() docstring):

- playability.py already rejects any candidate whose hand span
  is too wide for a comfortable position -- confirmed directly:
  the "0357" shape (a genuinely complete Cmaj7 voicing in
  aEADE, hand_span=4) is rejected with "Fret span too wide (4
  frets) for a single comfortable hand position". This is why
  BO already never selects an impractical up-the-neck-but-
  small-span shape merely to achieve completeness -- an
  existing mechanism, not something this task needed to add.

- The actual gap: music.classify_voicing_quality()'s coverage
  bonus weighted every covered tone equally (+2.0 each,
  including the non-defining perfect 5th), so a voicing that
  kept the 5th but dropped a defining tone (e.g. Cmaj7's 7th)
  scored identically to one that kept every defining tone but
  dropped the 5th. Fixed: the non-defining perfect 5th (the one
  interval defining_tones() itself already excludes from
  "defining" -- see that function's own docstring) now
  contributes less (+0.5) than root or any defining tone
  (+2.0), so a fallback voicing correctly prefers retaining
  defining tones over the 5th when both aren't available
  together. Reuses the existing defining_tones() function --
  nothing chord-specific is hardcoded.
"""

import xml.etree.ElementTree as ET

from tunings import get_tunings

from chord_service import ChordService

from chord_library import ChordLibrary

from chord_generator import generate_candidates

from fretboard import sounding_notes

from music import chord_tones, defining_tones, classify_voicing_quality

from models import Harmony

from score_generator import _apply_chord_shapes


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]


def _get_chord_service():

    return ChordService(ChordLibrary())


def _coverage(tuning, shape_text, root_pc, quality_code):

    notes = sounding_notes(tuning, shape_text)

    sounding_pcs = {note.pitch_class for note in notes}

    required = set(chord_tones(root_pc, quality_code))

    return sounding_pcs, required


# ---------------------------------------------------------
# 1 -- normal, complete chords unaffected (BO-18's own cases,
# re-verified after this follow-up's change)
# ---------------------------------------------------------

def test_c_major_in_aeade_still_complete():

    service = _get_chord_service()

    shapes = service.get_shapes(
        A_MODAL_SAWMILL, "C", 0, "", "Major"
    )

    sounding_pcs, required = _coverage(
        A_MODAL_SAWMILL, shapes[0].shape, 0, ""
    )

    assert required <= sounding_pcs, (
        f"C major top shape {shapes[0].shape!r} no longer "
        f"covers every chord tone -- required {sorted(required)}, "
        f"got {sorted(sounding_pcs)}"
    )


def test_em_in_aeade_still_complete():

    service = _get_chord_service()

    shapes = service.get_shapes(
        A_MODAL_SAWMILL, "E", 4, "m", "Minor"
    )

    sounding_pcs, required = _coverage(
        A_MODAL_SAWMILL, shapes[0].shape, 4, "m"
    )

    assert required <= sounding_pcs, (
        f"E minor top shape {shapes[0].shape!r} no longer "
        f"covers every chord tone -- required {sorted(required)}, "
        f"got {sorted(sounding_pcs)}"
    )


# ---------------------------------------------------------
# 2 -- the specifically reported impractical case
# ---------------------------------------------------------

def test_cmaj7_in_aeade_has_no_practical_complete_voicing():
    """
    Confirms the actual, underlying fact this whole task is
    about, directly: no candidate BO's own generator produces
    for Cmaj7 in aEADE covers all four chord tones (root, 3rd,
    5th, 7th) within the practical search window. If this ever
    starts failing, that's a real change in the generator's
    search range/tuning data worth knowing about on its own
    terms, not something to quietly accommodate.
    """

    candidates = generate_candidates(
        tuning=A_MODAL_SAWMILL, root="C", root_pc=0,
        quality_code="maj7", quality_display="Maj 7",
        max_candidates=100
    )

    assert candidates, "no Cmaj7 candidates generated at all"

    required = set(chord_tones(0, "maj7"))

    for candidate in candidates:

        sounding_pcs, _ = _coverage(
            A_MODAL_SAWMILL, candidate.shape, 0, "maj7"
        )

        assert not (required <= sounding_pcs), (
            f"expected no complete Cmaj7 candidate in aEADE, but "
            f"{candidate.shape!r} covers all of {sorted(required)} "
            f"-- if a practical complete voicing now exists, that's "
            f"good news, but this test (and the fallback behavior "
            f"it protects) needs to be revisited"
        )


def test_cmaj7_in_aeade_falls_back_to_practical_triad():
    """
    The exact reported behavior: BO should not chase an
    impractical up-the-neck "complete" voicing -- it should land
    on a practical, low-position, root-present voicing, even
    though it necessarily omits the 7th. This matches what the
    user explicitly confirmed is a reasonable outcome: "Cmaj7
    may reasonably become a C major triad if the major-7th
    cannot be included practically."
    """

    service = _get_chord_service()

    shapes = service.get_shapes(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Maj 7"
    )

    assert shapes, "no shapes returned for Cmaj7 in aEADE"

    top_shape = shapes[0]

    sounding_pcs, required = _coverage(
        A_MODAL_SAWMILL, top_shape.shape, 0, "maj7"
    )

    # Root and 3rd (the defining tone that's actually achievable
    # here -- see test_cmaj7_practical_voicing_prefers_defining_
    # tones_over_fifth below for the case where BOTH the 5th and
    # a defining tone are in contention) must be present.
    assert 0 in sounding_pcs  # root (C)

    assert 4 in sounding_pcs  # 3rd (E) -- a defining tone

    # And it must be a genuinely practical, low-position shape --
    # not the kind of extreme position the user flagged (e.g.
    # "0-10-9-8"). hand_span here is on the WRITTEN shape itself,
    # matching playability.py's own already-established
    # "comfortable hand position" check.
    from fretboard import parse_shape
    from chord_generator import hand_span

    values = parse_shape(top_shape.shape)

    assert hand_span(values) <= 3, (
        f"selected fallback shape {top_shape.shape!r} has a "
        f"hand span of {hand_span(values)} -- not the practical, "
        f"comfortable voicing this fallback is supposed to prefer"
    )


def test_cmaj7_diagram_accurately_represents_selected_notes():
    """
    The most important requirement: the generated FretDiagram
    must accurately represent the notes actually selected, not
    silently claim completeness it doesn't have. Traces the
    full pipeline (chord symbol -> chord_service -> written
    FretDiagram XML) and confirms the WRITTEN shape decodes to
    exactly the notes chord_service selected -- nothing added,
    nothing hidden, no relabeling.
    """

    service = _get_chord_service()

    root_pc, quality_code, quality_display = 0, "maj7", "Maj 7"

    expected_shapes = service.get_shapes(
        A_MODAL_SAWMILL, "C", root_pc, quality_code,
        quality_display
    )

    expected_shape_text = expected_shapes[0].shape

    staff = ET.Element("Staff")

    measure = ET.SubElement(staff, "Measure")

    voice = ET.SubElement(measure, "voice")

    ET.SubElement(voice, "Harmony")

    harmony = Harmony(
        measure=1, root_pc=root_pc, quality_code=quality_code,
        symbol="Cmaj7"
    )

    applied, skipped, _exceptions = _apply_chord_shapes(
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
        f"FretDiagram XML decoded to {written_shape_text!r}, but "
        f"chord_service selected {expected_shape_text!r} -- the "
        f"diagram doesn't accurately represent the selected notes"
    )

    # The chord symbol itself must remain untouched -- BO does
    # not relabel "Cmaj7" as "C" just because the voicing omits
    # the 7th. This is inherent to how _apply_chord_shapes()
    # works (it never touches the Harmony's own text), verified
    # directly here rather than assumed.
    harmony_element = staff.find(".//{*}Harmony")

    assert harmony_element is not None

    # No text content was ever added to the Harmony element by
    # chord-shape generation -- confirms the symbol itself is
    # left exactly as the source score wrote it.
    assert len(list(harmony_element)) == 0


# ---------------------------------------------------------
# 3 -- the actual fix, tested directly and precisely: when a
# fallback must omit a tone, it prefers omitting the
# non-defining perfect 5th over a genuinely defining tone
# ---------------------------------------------------------

def test_voicing_quality_prefers_defining_tones_over_fifth():
    """
    Direct, synthetic verification of the scoring fix itself
    (see this module's own docstring for why a real end-to-end
    example proved hard to find in this project's current
    tunings -- the 5th tends to be reachable on most strings in
    practice, making "keep defining tones, drop the 5th"
    candidates rare, not nonexistent). Two hypothetical voicings
    with the SAME tone count (3) but different composition:
    root+3rd+7th (omitting the non-defining 5th) must score
    higher than root+3rd+5th (omitting the defining 7th).
    """

    root_pc = 0  # C

    quality_code = "maj7"

    tones = set(chord_tones(root_pc, quality_code))

    defining = set(defining_tones(root_pc, quality_code))

    fifth_pc = (root_pc + 7) % 12

    assert fifth_pc not in defining, (
        "test setup assumption broken: the perfect 5th is "
        "expected to be excluded from defining_tones()"
    )

    non_fifth_defining_tones = sorted(defining - {fifth_pc})

    assert len(non_fifth_defining_tones) >= 2, (
        "test setup assumption broken: maj7 is expected to have "
        "at least two defining tones (3rd and 7th) besides the "
        "5th"
    )

    # root + BOTH defining tones (3rd, 7th), omitting the
    # non-defining 5th entirely.
    root_plus_defining = frozenset(
        {root_pc} | set(non_fifth_defining_tones)
    )

    # root + the 5th + only ONE defining tone (mirrors the real
    # "0350" case: root+3rd+5th, omitting the 7th) -- same total
    # tone count (3) as root_plus_defining above, so any score
    # difference comes purely from WHICH tones are kept, not how
    # many.
    root_plus_fifth_missing_a_defining_tone = frozenset(
        {root_pc, non_fifth_defining_tones[0], fifth_pc}
    )

    category_a, score_a = classify_voicing_quality(
        root_pc, quality_code, root_plus_defining
    )

    category_b, score_b = classify_voicing_quality(
        root_pc, quality_code,
        root_plus_fifth_missing_a_defining_tone
    )

    # Same category (both ROOT_PRESENT) -- the distinction must
    # come from the score, not the category.
    assert category_a == category_b

    assert score_a > score_b, (
        f"a voicing keeping root+defining tones "
        f"({sorted(root_plus_defining)}, score={score_a}) should "
        f"score higher than one keeping the non-defining 5th "
        f"instead of a defining tone "
        f"({sorted(root_plus_fifth_missing_a_defining_tone)}, "
        f"score={score_b})"
    )


def test_defining_tones_still_excludes_perfect_fifth():
    """
    Sanity check on the assumption the fix above relies on --
    confirms defining_tones() genuinely excludes the perfect
    5th for a representative spread of qualities, not just
    maj7. If this behavior ever changes, the fix's own rationale
    needs revisiting.
    """

    for root_pc in (0, 4, 7):

        for quality_code in ("", "m", "7", "maj7", "m7"):

            tones = chord_tones(root_pc, quality_code)

            if tones is None:

                continue

            defining = defining_tones(root_pc, quality_code)

            fifth_pc = (root_pc + 7) % 12

            if fifth_pc in tones and len(tones) > 2:

                assert fifth_pc not in defining, (
                    f"root_pc={root_pc} quality={quality_code!r}: "
                    f"expected the perfect 5th to be excluded "
                    f"from defining tones"
                )
