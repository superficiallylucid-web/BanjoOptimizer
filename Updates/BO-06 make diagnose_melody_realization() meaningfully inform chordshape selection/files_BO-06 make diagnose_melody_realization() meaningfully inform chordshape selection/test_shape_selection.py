"""
tests/test_shape_selection.py

Tests for the 3-tier melody realization classification
(fretboard.classify_melody_realization) and its use in
chord_service.select_shape_for_melody() -- picking a single
best shape per chord+melody occurrence and making explicit how
well it actually realizes the melody, rather than treating
"playable" and "realizes the melody" as the same thing.
"""

from tunings import get_tunings

from models import ChordShape

from chord_library import ChordLibrary

from chord_service import (
    ChordService,
    CHORD_TONE_AND_USABLE_VOICING,
    CHORD_TONE_BUT_NO_USABLE_VOICING,
    NOT_A_CHORD_TONE
)

from fretboard import (
    classify_melody_realization,
    DIRECT_REALIZATION,
    INDIRECT_REALIZATION,
    NO_REALIZATION
)


OPEN_G = get_tunings()["Open G"]

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE


def _shape(shape_text, source):

    return ChordShape(
        tuning="gDGBD",
        root="C",
        quality="Major",
        shape=shape_text,
        source=source
    )


def _service():

    return ChordService(ChordLibrary())


def _service_returning(fixed_shapes):

    service = _service()

    service.get_shapes = lambda *args, **kwargs: fixed_shapes

    return service


# ---------------------------------------------------------
# 1 -- direct melody realization
# ---------------------------------------------------------
#
# 2012 on Open G: E3 G3 C4 E4 -- top note is E4, so melody "E"
# is directly realized as the lead voice.

def test_direct_melody_realization():

    assert (
        classify_melody_realization(OPEN_G, "2012", "E")
        == DIRECT_REALIZATION
    )

    service = _service()

    result = service.select_shape_for_melody(
        OPEN_G, "C", 0, "", "Major", "E"
    )

    assert result.selected_shape.shape == "2012"

    assert result.realization_tier == DIRECT_REALIZATION

    assert result.diagnosis.category == (
        CHORD_TONE_AND_USABLE_VOICING
    )


# ---------------------------------------------------------
# 2 -- melody present as an inner voice
# ---------------------------------------------------------
#
# The real My Favorite Things case: Cmaj7/aEADE, melody B3,
# the actual shape the arranger used (0220) is honestly
# INDIRECT -- B3 sounds (string 1), but the top note is E4,
# not B3.

def test_melody_present_as_inner_voice():

    assert (
        classify_melody_realization(A_MODAL_SAWMILL, "0220", "B3")
        == INDIRECT_REALIZATION
    )

    service = _service()

    result = service.select_shape_for_melody(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Maj 7", "B3"
    )

    assert result.selected_shape.shape == "0220"

    assert result.realization_tier == INDIRECT_REALIZATION

    # Still a real, usable realization -- just not the lead
    # voice. The aggregate diagnosis should say so.
    assert result.diagnosis.category == (
        CHORD_TONE_AND_USABLE_VOICING
    )


# ---------------------------------------------------------
# 3 -- melody absent: a real chord tone, but none of the
# available shapes realize it anywhere
# ---------------------------------------------------------
#
# Reuses the same real, honest example established two tasks
# ago: the top-2 ranked Cmaj7/aEADE shapes (0320, 0350) are
# both ROOT_PRESENT/high quality, but neither one sounds B
# anywhere.

def test_melody_absent_from_available_shapes():

    for shape_text in ("0320", "0350"):

        assert (
            classify_melody_realization(
                A_MODAL_SAWMILL, shape_text, "B3"
            )
            == NO_REALIZATION
        )

    shapes = [
        _shape("0320", "generated"),
        _shape("0350", "generated"),
    ]

    service = _service_returning(shapes)

    result = service.select_shape_for_melody(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Maj 7", "B3"
    )

    # Still returns the best available shape -- honestly
    # labeled as not realizing the melody, not silently
    # presented as if it did.
    assert result.selected_shape is not None

    assert result.realization_tier == NO_REALIZATION

    assert result.diagnosis.category == (
        CHORD_TONE_BUT_NO_USABLE_VOICING
    )


# ---------------------------------------------------------
# 4 -- impossible chord/melody combination: melody isn't
# even a theoretical chord tone
# ---------------------------------------------------------

def test_impossible_chord_melody_combination():

    service = _service()

    result = service.select_shape_for_melody(
        A_MODAL_SAWMILL, "C", 0, "maj7", "Maj 7", "D"
    )

    # A shape is still selected (the best playable Cmaj7 shape
    # overall) -- but both signals make clear it doesn't
    # realize this melody note, since D was never part of the
    # chord to begin with.
    assert result.selected_shape is not None

    assert result.realization_tier == NO_REALIZATION

    assert result.diagnosis.category == NOT_A_CHORD_TONE


# ---------------------------------------------------------
# 5 -- multiple shapes possible; the best melodic realization
# wins, not merely the most playable one
# ---------------------------------------------------------
#
# Real Open G data: 2012 (top E4, DIRECT for melody E) vs.
# 5555/5055 (top G4, only INDIRECT for melody E, despite E
# sounding in them too). The direct realization must be
# selected first even though all are playable candidates.

def test_best_melodic_realization_wins_among_multiple_shapes():

    service = _service()

    shapes = service.get_shapes(OPEN_G, "C", 0, "", "Major")

    shape_texts = {s.shape for s in shapes}

    assert {"2012", "5555", "5055"}.issubset(shape_texts), (
        "expected the known real candidate set for this test "
        "to be stable"
    )

    result = service.select_shape_for_melody(
        OPEN_G, "C", 0, "", "Major", "E"
    )

    assert result.selected_shape.shape == "2012"

    assert result.realization_tier == DIRECT_REALIZATION

    # Confirm the alternatives really were merely playable,
    # not equally good realizations -- otherwise this test
    # wouldn't actually prove tier beats raw playability.
    for shape in shapes:

        if shape.shape in ("5555", "5055"):

            assert classify_melody_realization(
                OPEN_G, shape.shape, "E"
            ) == INDIRECT_REALIZATION
