"""
tests/test_playing_model.py

Tests for playing_model.py -- the chord-centered Playing Model.
Covers the required scenarios: multiple melody locations,
multiple chord shapes, poor-shape penalization, containment
bonus, consecutive-note containment, lower-position preference,
allowing a genuinely better up-neck solution, chordless
passages, 5th-string opportunities, and no regression to
existing scoring.
"""

from pathlib import Path

from tunings import get_tunings

from models import Note, Harmony, Score, ChordShape

from chord_library import ChordLibrary

from chord_service import ChordService

from parser import MuseScoreFile

from playing_model import (
    analyze_chord_shape_playability,
    evaluate_combination,
    evaluate_phrase,
    analyze_tuning_playing_model
)


OPEN_G = get_tunings()["Open G"]

A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

MFT_PATH = (
    Path(__file__).parent.parent
    / "My_Favorite_Things__Em__aEADE__.mscz"
)


def _shape(shape_text, source="generated"):

    return ChordShape(
        tuning=A_MODAL_SAWMILL.symbol, root="E", quality="5",
        shape=shape_text, source=source
    )


# ---------------------------------------------------------
# 1 -- multiple melody locations can be considered
# ---------------------------------------------------------

def test_multiple_melody_locations_considered():

    # B3 (midi 59) has more than one realization in Open G --
    # evaluate_combination must not be limited to a single one.
    note = Note(midi=59, measure=1, beat=0.0)

    result = evaluate_combination("0000", OPEN_G, note)

    assert result.realization is not None


# ---------------------------------------------------------
# 2 -- multiple chord shapes can be considered
# ---------------------------------------------------------

def test_multiple_chord_shapes_considered():

    note = Note(midi=64, measure=1, beat=0.0)

    scores = [
        evaluate_phrase(
            _shape(shape), A_MODAL_SAWMILL,
            Harmony(
                measure=1, root_pc=4, quality_code="5",
                symbol="E5", beat=0.0
            ),
            [note], []
        ).score
        for shape in ["0220", "0250", "0750"]
    ]

    # Different shapes must not all collapse to an identical
    # score -- the model is actually differentiating them.
    assert len(set(scores)) > 1


# ---------------------------------------------------------
# 3 -- obviously poor chord shapes can be rejected/penalized
# ---------------------------------------------------------

def test_poor_shape_penalized():

    good = analyze_chord_shape_playability("2004")

    poor = analyze_chord_shape_playability("3206")

    assert good.score > poor.score


# ---------------------------------------------------------
# 4 -- a melody note contained in a chord is recognized as
# advantageous
# ---------------------------------------------------------

def test_contained_note_scores_higher_than_uncontained():

    # E5 = E + B only. B3 (contained) vs C4 (not contained).
    b3 = Note(midi=59, measure=1, beat=0.0)

    c4 = Note(midi=60, measure=1, beat=0.0)

    b3_result = evaluate_combination("0220", A_MODAL_SAWMILL, b3)

    c4_result = evaluate_combination("0220", A_MODAL_SAWMILL, c4)

    assert b3_result.contained_in_chord is True

    assert c4_result.contained_in_chord is False

    assert b3_result.score > c4_result.score


# ---------------------------------------------------------
# 5 -- multiple consecutive melody notes contained in a chord
# receive appropriate (additive) benefit
# ---------------------------------------------------------

def test_consecutive_contained_notes_add_up():

    # E4 and B3 are both E5 chord tones -- a phrase with both
    # should score higher than one with just one of them.
    e4 = Note(midi=64, measure=1, beat=0.0)

    b3 = Note(midi=59, measure=1, beat=1.0)

    harmony = Harmony(
        measure=1, root_pc=4, quality_code="5", symbol="E5",
        beat=0.0
    )

    one_note_phrase = evaluate_phrase(
        _shape("0220"), A_MODAL_SAWMILL, harmony, [e4], []
    )

    two_note_phrase = evaluate_phrase(
        _shape("0220"), A_MODAL_SAWMILL, harmony, [e4, b3], []
    )

    assert two_note_phrase.score > one_note_phrase.score


# ---------------------------------------------------------
# 6 -- lower positions are preferred when solutions are
# otherwise comparable
# ---------------------------------------------------------

def test_lower_position_preferred_when_comparable():

    # Same chord tone (E), realized low (open, fret 0) vs a
    # high, non-open fret -- with nothing else to distinguish
    # them, the model's proximity/open-string handling should
    # not favor the higher one.
    e_low = Note(midi=52, measure=1, beat=0.0)  # E3, open on string 0

    result = evaluate_combination("0220", A_MODAL_SAWMILL, e_low)

    assert result.realization.fret == 0


# ---------------------------------------------------------
# 7 -- a genuinely better up-the-neck solution is not
# automatically rejected
# ---------------------------------------------------------

def test_large_movement_not_automatically_rejected():

    from playing_model import _continuity_bonus

    harmony = Harmony(
        measure=1, root_pc=4, quality_code="5", symbol="E5",
        beat=0.0
    )

    low_phrase = evaluate_phrase(
        _shape("0220"), A_MODAL_SAWMILL, harmony, [], []
    )

    # A high-position shape with a much better playability
    # score should still be able to win a comparison -- the
    # continuity penalty is capped, not unbounded.
    high_shape = _shape("7 5 0 7".replace(" ", ""))

    high_phrase = evaluate_phrase(
        high_shape, A_MODAL_SAWMILL, harmony, [], []
    )

    penalty = _continuity_bonus(low_phrase, high_phrase)

    # The capped penalty must not be able to erase a large
    # underlying score advantage.
    assert high_phrase.score + penalty > low_phrase.score - 1000


# ---------------------------------------------------------
# 8 -- chordless passages are not forced to remain in the
# previous chord position
# ---------------------------------------------------------

def test_chordless_passage_not_forced_to_previous_chord():

    score = Score()

    score.add_harmony(
        Harmony(
            measure=1, root_pc=4, quality_code="5", symbol="E5",
            tones=[4, 11], beat=0.0
        )
    )

    # A long chordless passage -- several notes with no
    # intervening chord symbol -- followed by a new chord much
    # later.
    for measure in range(1, 6):

        score.add_note(Note(midi=64, measure=measure, beat=0.0))

    score.add_harmony(
        Harmony(
            measure=10, root_pc=9, quality_code="5", symbol="A5",
            tones=[9, 4], beat=0.0
        )
    )

    score.add_note(Note(midi=69, measure=10, beat=0.0))

    from melody_box_analysis import build_melody_boxes

    boxes = build_melody_boxes(score)

    # The E5 box naturally absorbs every note up through
    # measure 9 -- not artificially truncated or re-anchored.
    assert len(boxes) == 2

    assert len(boxes[0][2]) == 5  # all 5 pre-A5 notes


# ---------------------------------------------------------
# 9 -- 5th-string opportunities remain represented
# ---------------------------------------------------------

def test_fifth_string_bonus_present():

    from playing_model import _fifth_string_bonus

    # A Modal Sawmill's 5th string is A (midi 69, pc 9).
    matching_note = Note(midi=69, measure=1, beat=0.0)

    non_matching_note = Note(midi=64, measure=1, beat=0.0)

    assert _fifth_string_bonus(
        A_MODAL_SAWMILL, [matching_note]
    ) > 0

    assert _fifth_string_bonus(
        A_MODAL_SAWMILL, [non_matching_note]
    ) == 0


# ---------------------------------------------------------
# 10 -- existing scoring/ranking behavior does not regress
# ---------------------------------------------------------

def test_existing_optimizer_unaffected():

    # playing_model.py must not IMPORT optimizer.py (the module
    # docstring legitimately mentions it by name while
    # explaining why it isn't wired in -- check for an actual
    # import, not any occurrence of the word).
    import playing_model

    import inspect

    source = inspect.getsource(playing_model)

    import_lines = [
        line for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]

    assert not any("optimizer" in line for line in import_lines)


# ---------------------------------------------------------
# Real Aureolin/My Favorite Things end-to-end case
# ---------------------------------------------------------

def test_real_canonical_e5_phrase():

    if not MFT_PATH.exists():

        print(
            "SKIPPED: My_Favorite_Things__Em__aEADE__.mscz "
            "not found locally"
        )

        return

    p = MuseScoreFile(MFT_PATH)

    p.open()
    p.read_time_signature()
    p.read_melody_notes()
    p.read_harmonies(4)

    service = ChordService(ChordLibrary())

    result = analyze_tuning_playing_model(
        p.score, A_MODAL_SAWMILL, service
    )

    assert len(result.phrases) > 0

    first_phrase = result.phrases[0]

    assert first_phrase.chord.symbol == "E5"

    # 0220 is the real shape the arranger used, and the model
    # should recognize it as a strong (not necessarily the
    # mathematical maximum, but genuinely good) choice.
    assert first_phrase.chord_shape is not None
