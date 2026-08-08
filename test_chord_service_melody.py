"""
tests/test_chord_service_melody.py

Tests for ChordService.get_shapes_for_melody() -- reordering
get_shapes()'s result to prefer shapes whose top note matches
a given melody note by pitch class, without changing which
shapes are included or introducing a new numerical score.

TEST C needs a VERIFIED shape with a real top_note to exercise
"generated match beats non-matching verified" -- but
chord_library.py never actually populates top_note on the
shapes it loads (confirmed by inspection; a separate, pre-
existing gap, not something this task touches). So these tests
monkey-patch ChordService.get_shapes() to return small, hand-
built ChordShape fixtures for each scenario, and test the real
(unmodified) get_shapes_for_melody() reordering logic against
them -- this tests the actual ordering rule directly and
reliably, rather than depending on real library data that
doesn't currently support the scenario.
"""

from models import ChordShape

from chord_service import ChordService


def _shape(shape_text, top_note, source):

    return ChordShape(
        tuning="gDGBD",
        root="C",
        quality="Major",
        shape=shape_text,
        source=source,
        top_note=top_note
    )


def _service_returning(fixed_shapes):
    """
    A ChordService whose get_shapes() always returns the given
    fixed list, so get_shapes_for_melody() can be tested against
    controlled input without depending on real library/generator
    data.
    """

    service = ChordService(chord_library=None)

    service.get_shapes = lambda *args, **kwargs: fixed_shapes

    return service


# ---------------------------------------------------------
# TEST A -- some shapes match, matches come first, relative
# order preserved within each group
# ---------------------------------------------------------

def test_a_matches_first_preserving_relative_order():

    shapes = [
        _shape("2012", "E4", "verified"),
        _shape("5055", "G4", "generated"),
        _shape("2552", "E4", "generated"),
        _shape("5555", "G4", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=None,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note="E"
    )

    result_shapes = [s.shape for s in result]

    assert result_shapes == ["2012", "2552", "5055", "5555"]


# ---------------------------------------------------------
# TEST B -- no shape matches, order is unchanged
# ---------------------------------------------------------

def test_b_no_match_leaves_order_unchanged():

    shapes = [
        _shape("2012", "E4", "verified"),
        _shape("5055", "G4", "generated"),
        _shape("5555", "G4", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=None,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note="D"
    )

    result_shapes = [s.shape for s in result]

    assert result_shapes == ["2012", "5055", "5555"]


# ---------------------------------------------------------
# TEST C -- a matching generated shape beats a non-matching
# verified shape; verified/generated order is NOT the primary
# sort key here, matching status is
# ---------------------------------------------------------

def test_c_matching_generated_beats_nonmatching_verified():

    shapes = [
        _shape("0000", "G4", "verified"),
        _shape("2012", "E4", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=None,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note="E"
    )

    assert result[0].shape == "2012"

    assert result[0].source == "generated"

    assert result[1].shape == "0000"

    assert result[1].source == "verified"


def test_c_both_match_keeps_original_relative_order():

    # If both shapes match, the original verified-first order
    # from get_shapes() must be preserved -- matching doesn't
    # reorder shapes that are already in the same group.
    shapes = [
        _shape("2012", "E4", "verified"),
        _shape("2552", "E4", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=None,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note="E"
    )

    assert [s.shape for s in result] == ["2012", "2552"]


# ---------------------------------------------------------
# TEST D -- matching is by pitch class, not exact octave
# ---------------------------------------------------------

def test_d_matches_by_pitch_class_not_octave():

    shapes = [
        _shape("5055", "G4", "generated"),
        _shape("2012", "E3", "verified"),
    ]

    service = _service_returning(shapes)

    # Melody note given WITH an octave (E4) must still match a
    # shape whose top note is a DIFFERENT octave (E3).
    result = service.get_shapes_for_melody(
        tuning=None,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note="E4"
    )

    assert result[0].shape == "2012"


# ---------------------------------------------------------
# TEST E -- no melody note falls back to get_shapes() order
# ---------------------------------------------------------

def test_e_no_melody_note_falls_back_to_existing_order():

    shapes = [
        _shape("2012", "E4", "verified"),
        _shape("5055", "G4", "generated"),
        _shape("5555", "G4", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=None,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note=None
    )

    assert [s.shape for s in result] == ["2012", "5055", "5555"]
