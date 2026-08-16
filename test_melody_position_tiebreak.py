"""
tests/test_melody_position_tiebreak.py

Regression tests for BO-22: chord-shape selection now uses the
melody note's likely fretboard position as a narrow tiebreaker
among candidates already tied on voicing quality and exact
melody-pitch containment.

Reuses existing machinery throughout, per the investigation's
own finding that the necessary concepts already existed --
nothing new was invented:

- fretboard.find_positions()/best_position() (unchanged) for
  the melody note's preferred string/fret.
- playing_model._chord_working_fret() (unchanged) for a chord
  shape's own hand-position anchor -- the lowest FRETTED value,
  open strings correctly excluded.
- A capped distance (POSITION_DISTANCE_CAP=5, matching
  playing_model.py's own CONTINUITY_MOVE_DAMPENING_START)
  between those two, inserted as priority 3 in the existing
  ranking -- AFTER category (1) and melody-pitch-containment
  (2), BEFORE the existing playability tiebreak (4, preserved
  automatically by Python's stable sort).

Real-world case (The Christmas Song, A Modal Sawmill/aEADE): the
Am chord at measure 6, beat 3.5 has melody note E4 at its onset.
Both "0,0,10,0" and "5,3,2,0" are complete (ROOT_PRESENT),
tied quality score (19.5), and both contain E4 exactly -- so the
positional tiebreak is what decides between them. Preferred
melody fret (via find_positions()/best_position(), unchanged)
is 2; "5,3,2,0"'s working fret is 2 (distance 0), "0,0,10,0"'s
is 10 (distance 8, capped to 5) -- "5,3,2,0" wins.
"""

import xml.etree.ElementTree as ET

from tunings import get_tunings

from models import ChordShape, Note, Harmony

from chord_library import ChordLibrary

from chord_service import ChordService, _capped_position_distance

from fretboard import sounding_notes, find_positions, best_position

from score_generator import _apply_chord_shapes, _preferred_melody_fret


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE


def _get_chord_service():

    return ChordService(ChordLibrary())


def _mock_shape(shape_text, category, quality_score):

    shape = ChordShape(
        tuning="aEADE", root="A", quality="Minor",
        shape=shape_text, source="generated"
    )

    shape.voicing_quality_category = category

    shape.voicing_quality_score = quality_score

    return shape


def _service_returning(fixed_shapes):

    service = _get_chord_service()

    service.get_shapes = lambda *args, **kwargs: fixed_shapes

    return service


# ---------------------------------------------------------
# 1 -- the real Am case: 5,3,2,0 beats 0,0,10,0
# ---------------------------------------------------------

def test_real_am_case_5320_beats_00100():

    service = _get_chord_service()

    # Confirmed real values: melody E4 (64), preferred fret 2
    # (find_positions()/best_position(), unchanged).
    open_notes = A_MODAL_SAWMILL.notes[1:]

    positions = find_positions(64, open_notes)

    preferred_fret = best_position(positions)["fret"]

    assert preferred_fret == 2

    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=preferred_fret
    )

    assert shapes[0].shape == "5320"

    notes = sounding_notes(A_MODAL_SAWMILL, shapes[0].shape)

    assert any(n.midi == 64 for n in notes)

    sounding_pcs = {n.pitch_class for n in notes}

    assert {9, 0, 4} <= sounding_pcs  # still a valid Am triad

    # Without the new parameter, BO-20/21's own prior behavior
    # is completely unaffected.
    shapes_unaffected = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64}
    )

    assert shapes_unaffected[0].shape == "00(10)0"


# ---------------------------------------------------------
# 2 -- direct positional tiebreaker test
# ---------------------------------------------------------

def test_positional_tiebreaker_direct():

    # Two candidates, constructed directly, tied on category and
    # quality score and both containing the melody pitch --
    # position must be the deciding factor.
    close_shape = _mock_shape("5320", "ROOT_PRESENT", 19.5)

    far_shape = _mock_shape("00(10)0", "ROOT_PRESENT", 19.5)

    service = _service_returning([far_shape, close_shape])

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2
    )

    assert ranked[0].shape == "5320"

    # And the distance computation itself, directly.
    assert _capped_position_distance(close_shape, 2) == 0

    assert _capped_position_distance(far_shape, 2) == 5  # capped from 8


# ---------------------------------------------------------
# 3 -- musical priority must win: quality beats position
# ---------------------------------------------------------

def test_quality_beats_positional_proximity():

    # A ROOTLESS_STRONG shape very close to the melody position
    # must NOT beat a ROOT_PRESENT shape far from it.
    close_but_incomplete = _mock_shape(
        "0320", "ROOTLESS_STRONG", 8.5
    )

    far_but_complete = _mock_shape(
        "00(10)0", "ROOT_PRESENT", 19.5
    )

    service = _service_returning(
        [close_but_incomplete, far_but_complete]
    )

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2
    )

    assert ranked[0].shape == "00(10)0", (
        "a lower-quality chord must never beat a higher-quality "
        "chord merely because its position is closer to the "
        "melody"
    )


# ---------------------------------------------------------
# 4 -- melody match must win: containment beats position
# ---------------------------------------------------------

def test_melody_match_beats_positional_proximity():

    # A same-category shape that does NOT contain the melody
    # pitch (verified directly: "5075" sounds A3,A3,A4,A4 --
    # no E4 at all), but is very close positionally, must not
    # beat one that DOES contain it but is farther.
    close_no_melody = _mock_shape("5075", "ROOT_PRESENT", 17.0)

    far_with_melody = _mock_shape("00(10)0", "ROOT_PRESENT", 19.5)

    service = _service_returning(
        [close_no_melody, far_with_melody]
    )

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=3
    )

    assert ranked[0].shape == "00(10)0", (
        "a shape containing the required exact melody pitch "
        "must still beat an otherwise comparable shape that "
        "does not, even if the non-matching shape is closer in "
        "position"
    )


# ---------------------------------------------------------
# 5 -- no preferred position: behavior remains stable
# ---------------------------------------------------------

def test_no_preferred_position_stable_behavior():

    service = _get_chord_service()

    shapes_no_pref = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64}
    )

    shapes_explicit_none = (
        service.get_shapes_for_exact_melody_pitch(
            A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64},
            preferred_melody_fret=None
        )
    )

    assert [s.shape for s in shapes_no_pref] == [
        s.shape for s in shapes_explicit_none
    ]

    # _preferred_melody_fret() itself returns None gracefully
    # for an empty onset list.
    assert _preferred_melody_fret([], A_MODAL_SAWMILL) is None


# ---------------------------------------------------------
# 6 -- open-string melody: an open melody note doesn't force
# an inappropriate all-open/fret-0 chord shape
# ---------------------------------------------------------

def test_open_melody_note_does_not_force_all_open_shape():
    """
    E4 is also playable as an open string (string 3, fret 0) in
    aEADE. Confirms that when the melody is open, the positional
    tiebreak (working fret 0, since an all-open candidate has no
    FRETTED working position -- see _capped_position_distance's
    own neutral-distance handling) doesn't cause BO to select an
    inappropriate all-open voicing when musical/voicing criteria
    (category, quality score) favor a different, fretted one.
    """

    # An all-open shape (category ROOT_PRESENT if it happens to
    # cover the root) vs a fretted, higher-quality shape near a
    # LOW preferred fret -- quality must still decide, exactly
    # as test_quality_beats_positional_proximity already proves
    # for the general case. Confirmed directly for the specific
    # "melody realized as an open string" scenario:
    lower_quality_shape = _mock_shape(
        "0070", "ROOT_PRESENT", 17.5
    )

    fretted_higher_quality = _mock_shape(
        "5320", "ROOT_PRESENT", 19.5
    )

    service = _service_returning(
        [fretted_higher_quality, lower_quality_shape]
    )

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=0
    )

    assert ranked[0].shape == "5320", (
        "quality must still decide even when the melody's own "
        "preferred position is fret 0 (open) -- an all-open "
        "shape isn't automatically preferred just because it "
        "technically has zero positional distance"
    )

    # And _capped_position_distance() itself treats a genuinely
    # all-open shape as neutral (0), not literally "at fret 0" --
    # an important distinction per this task's own instruction
    # not to treat open-string working position as fret 0.
    all_open_shape = _mock_shape("0000", "ROOT_PRESENT", 15.0)

    assert _capped_position_distance(all_open_shape, 5) == 0


# ---------------------------------------------------------
# 7 -- full pipeline / real fixture regression
# ---------------------------------------------------------

def test_full_pipeline_real_am_chord_selects_5320():

    staff = ET.Element("Staff")

    measure = ET.SubElement(staff, "Measure")

    voice = ET.SubElement(measure, "voice")

    ET.SubElement(voice, "Harmony")

    harmony = Harmony(
        measure=6, beat=3.5, root_pc=9, quality_code="m",
        symbol="Am"
    )

    melody_notes = [Note(midi=64, measure=6, beat=3.5)]

    service = _get_chord_service()

    applied, skipped, exceptions = _apply_chord_shapes(
        staff, [harmony], A_MODAL_SAWMILL, service,
        melody_notes=melody_notes
    )

    assert applied == 1

    assert exceptions == []  # a practical match was found

    fret_diagram = staff.find(".//{*}FretDiagram")

    fret_offset_element = fret_diagram.find("{*}fretOffset")

    fret_offset = (
        int(fret_offset_element.text)
        if fret_offset_element is not None else 0
    )

    frets_element = fret_diagram.find("{*}frets")

    assert frets_element.text == "4"

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

    assert [values[i] for i in range(4)] == [5, 3, 2, 0]


# ---------------------------------------------------------
# BO-22-FOLLOWUP: quality_score must participate in the sort
# key BEFORE positional distance, so a real quality difference
# can never be overridden by a small positional advantage.
#
# Bug found by direct investigation: for Cmaj7 in aEADE with
# melody B4, the sort key previously only checked category
# (coarse) and melody-match before position, never the finer
# quality_score -- so a complete C-E-G-B voicing (quality_score
# 21.5) lost to an incomplete C-E-B voicing (quality_score 21.0,
# missing G) purely because the incomplete one's working fret
# (7) was one fret closer to the melody's preferred position
# than the complete one's (8). These tests would fail if that
# old ordering were restored.
# ---------------------------------------------------------

def test_real_cmaj7_case_complete_voicing_beats_closer_incomplete_one():

    service = _get_chord_service()

    # Confirmed real values: melody B4 (71), preferred fret 7
    # (find_positions()/best_position(), unchanged).
    open_notes = A_MODAL_SAWMILL.notes[1:]

    positions = find_positions(71, open_notes)

    preferred_fret = best_position(positions)["fret"]

    assert preferred_fret == 7

    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Maj 7", {71},
        preferred_melody_fret=preferred_fret
    )

    top_shape = shapes[0]

    notes = sounding_notes(A_MODAL_SAWMILL, top_shape.shape)

    sounding_pcs = {n.pitch_class for n in notes}

    assert {0, 4, 7, 11} <= sounding_pcs, (
        f"expected a complete Cmaj7 voicing (C,E,G,B), got "
        f"{top_shape.shape!r} sounding {sorted(sounding_pcs)} -- "
        f"an incomplete voicing must not win purely on a small "
        f"positional advantage"
    )

    assert any(n.midi == 71 for n in notes)

    # The specific, previously-losing complete candidates must
    # now be ahead of the previously-winning incomplete one.
    shape_order = [s.shape for s in shapes]

    assert shape_order.index("0(10)98") < shape_order.index(
        "0798"
    )


def test_quality_score_participates_before_positional_distance():

    # Constructed directly: two candidates, SAME category, BOTH
    # contain the melody pitch, but DIFFERENT quality_score --
    # and the LOWER-quality one is positioned closer to the
    # melody. The higher-quality one must still win.
    lower_quality_closer = _mock_shape(
        "0798", "ROOT_PRESENT", 21.0
    )

    higher_quality_farther = _mock_shape(
        "0(10)98", "ROOT_PRESENT", 21.5
    )

    service = _service_returning(
        [lower_quality_closer, higher_quality_farther]
    )

    ranked = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Maj 7", {71},
        preferred_melody_fret=7
    )

    assert ranked[0].shape == "0(10)98", (
        "a candidate with a higher quality_score must win before "
        "positional distance is ever consulted, even when the "
        "lower-quality candidate sits closer to the melody "
        "position"
    )


def test_positional_tiebreak_still_applies_among_equal_quality():
    """
    Confirms the fix didn't remove positional tie-breaking
    entirely -- it only moved it after quality_score. Two
    candidates with IDENTICAL quality_score (the real Am/E4
    case, unaffected by this fix) must still be decided by
    position, exactly as BO-22 originally established.
    """

    service = _get_chord_service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        A_MODAL_SAWMILL, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2
    )

    assert shapes[0].shape == "5320"

