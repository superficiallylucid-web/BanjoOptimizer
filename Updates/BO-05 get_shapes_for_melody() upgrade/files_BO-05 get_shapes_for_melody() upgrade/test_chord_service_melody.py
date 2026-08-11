"""
tests/test_chord_service_melody.py

Tests for ChordService.get_shapes_for_melody() -- reordering
get_shapes()'s result to prefer shapes that sound a given
melody note ANYWHERE (any string, not just the top note),
without changing which shapes are included or introducing a
new numerical score.

Uses find_melody_occurrences() for the match check (see
fretboard.py), so fixtures need a REAL tuning and shape strings
whose actual sounding notes genuinely produce the intended
match/non-match outcome -- unlike an earlier version of this
file, which only needed a claimed top_note string and could use
tuning=None. All shape->sounding-note claims below are verified
directly against Open G before being used (see the sounding_notes
values in each test's comment).
"""

from tunings import get_tunings

from models import ChordShape

from chord_service import ChordService


OPEN_G = get_tunings()["Open G"]


def _shape(shape_text, source):

    return ChordShape(
        tuning="gDGBD",
        root="C",
        quality="Major",
        shape=shape_text,
        source=source
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
#
# Real sounding notes (Open G), confirmed:
#   2012: E3 G3 C4 E4  -- has E
#   0000: D3 G3 B3 D4  -- no E
#   2552: E3 C4 E4 E4  -- has E
#   0030: D3 G3 D4 D4  -- no E

def test_a_matches_first_preserving_relative_order():

    shapes = [
        _shape("2012", "verified"),
        _shape("0000", "generated"),
        _shape("2552", "generated"),
        _shape("0030", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=OPEN_G,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note="E"
    )

    result_shapes = [s.shape for s in result]

    assert result_shapes == ["2012", "2552", "0000", "0030"]


# ---------------------------------------------------------
# TEST B -- no shape matches, order is unchanged
# ---------------------------------------------------------
#
# melody "F" doesn't occur in any of these (2012: E G C E,
# 0000: D G B D, 0030: D G D D) -- none contain F.

def test_b_no_match_leaves_order_unchanged():

    shapes = [
        _shape("2012", "verified"),
        _shape("0000", "generated"),
        _shape("0030", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=OPEN_G,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note="F"
    )

    result_shapes = [s.shape for s in result]

    assert result_shapes == ["2012", "0000", "0030"]


# ---------------------------------------------------------
# TEST C -- a matching generated shape beats a non-matching
# verified shape; matching status is the primary sort key,
# not source
# ---------------------------------------------------------

def test_c_matching_generated_beats_nonmatching_verified():

    # 0000 (verified): D3 G3 B3 D4 -- no E.
    # 2012 (generated): E3 G3 C4 E4 -- has E.
    shapes = [
        _shape("0000", "verified"),
        _shape("2012", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=OPEN_G,
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

    # Both 2012 and 2552 contain E -- if both match, the
    # original verified-first order from get_shapes() must be
    # preserved, not reshuffled.
    shapes = [
        _shape("2012", "verified"),
        _shape("2552", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=OPEN_G,
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
#
# "2300": E3 A#3 B3 D4 -- contains E3 only (no E4 anywhere).
# Melody note given WITH an octave (E4) must still match,
# since only the pitch class matters.

def test_d_matches_by_pitch_class_not_octave():

    shapes = [
        _shape("0000", "generated"),  # D3 G3 B3 D4 -- no E
        _shape("2300", "verified"),   # E3 A#3 B3 D4 -- E3 only
    ]

    service = _service_returning(shapes)

    result = service.get_shapes_for_melody(
        tuning=OPEN_G,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note="E4"
    )

    assert result[0].shape == "2300"


# ---------------------------------------------------------
# TEST E -- no melody note falls back to get_shapes() order
# ---------------------------------------------------------
#
# melody_note=None returns early, before tuning is ever used
# -- tuning=None is safe here specifically because of that
# early return, not because matching tolerates it generally.

def test_e_no_melody_note_falls_back_to_existing_order():

    shapes = [
        _shape("2012", "verified"),
        _shape("0000", "generated"),
        _shape("0030", "generated"),
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

    assert [s.shape for s in result] == ["2012", "0000", "0030"]
