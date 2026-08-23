"""
tests/test_chord_vocabulary_analysis.py

Tests for chord_vocabulary_analysis.py -- extracting a score's
distinct chord+melody vocabulary and analyzing it against a
tuning, as evidence for comparing tunings. No verdict-picking
logic to test here (there isn't any); these tests confirm the
extraction/analysis itself is correct.

Uses a small synthetic Score (built directly from Harmony/Note,
same pattern as other tests in this project) for the
deduplication tests, real Open G data for the per-chord
analysis test, and the real My Favorite Things file (aDADE vs
aEADE) for the end-to-end comparison -- skips gracefully if
that file isn't present locally, matching the pattern already
used elsewhere in this project.
"""

from pathlib import Path

from models import Score, Note, Harmony

from tunings import get_tunings

from chord_library import ChordLibrary

from chord_service import ChordService

from parser import MuseScoreFile

from music import quality_code_to_display_name

from chord_vocabulary_analysis import (
    extract_chord_vocabulary,
    analyze_chord_for_tuning,
    analyze_score_for_tuning
)


OPEN_G = get_tunings()["Open G"]

MFT_PATH = (
    Path(__file__).parent.parent
    / "My_Favorite_Things__Em__aEADE__.mscz"
)


def _service():

    return ChordService(ChordLibrary())


# ---------------------------------------------------------
# quality_code_to_display_name
# ---------------------------------------------------------

def test_quality_code_to_display_name_known_codes():

    assert quality_code_to_display_name("") == "Major"

    assert quality_code_to_display_name("maj7") == "Maj 7"

    assert quality_code_to_display_name("mb5") == "dim"


def test_quality_code_to_display_name_unknown_code():

    assert quality_code_to_display_name("nonsense") is None


# ---------------------------------------------------------
# extract_chord_vocabulary -- deduplication
# ---------------------------------------------------------

def _synthetic_score():
    """
    A small synthetic score: the same chord occurs 3 times
    with the same melody note (should collapse to 1 vocabulary
    entry with occurrence_count=3), plus one occurrence of the
    same chord with a DIFFERENT melody note (a separate entry),
    plus one occurrence with no melody note at all at that
    beat (also a separate entry).
    """

    score = Score()

    # C major, melody E, at three different positions
    for measure, beat, midi in [(1, 0.0, 64), (3, 0.0, 64), (5, 0.0, 64)]:

        score.add_harmony(
            Harmony(
                measure=measure, root_pc=0, quality_code="",
                symbol="C", tones=[0, 4, 7], beat=beat
            )
        )

        score.add_note(Note(midi=midi, measure=measure, beat=beat))

    # C major, melody G (different pitch class), at measure 7
    score.add_harmony(
        Harmony(
            measure=7, root_pc=0, quality_code="",
            symbol="C", tones=[0, 4, 7], beat=0.0
        )
    )

    score.add_note(Note(midi=67, measure=7, beat=0.0))

    # C major with no notes anywhere in this measure at all --
    # melody_note_for_harmony() has nothing to find, so this is
    # a genuinely unambiguous "no melody note" case, distinct
    # from both entries above.
    score.add_harmony(
        Harmony(
            measure=11, root_pc=0, quality_code="",
            symbol="C", tones=[0, 4, 7], beat=0.0
        )
    )

    return score


def test_vocabulary_deduplicates_repeated_combinations():

    score = _synthetic_score()

    vocabulary = extract_chord_vocabulary(score)

    # 3 distinct entries: (C, melody E), (C, melody G),
    # (C, no melody note)
    assert len(vocabulary) == 3

    by_pc = {
        entry["melody_pitch_class"]: entry for entry in vocabulary
    }

    assert 4 in by_pc  # E

    assert 7 in by_pc  # G

    assert None in by_pc  # no melody note


def test_vocabulary_occurrence_count_reflects_repetition():

    score = _synthetic_score()

    vocabulary = extract_chord_vocabulary(score)

    melody_e_entry = [
        e for e in vocabulary if e["melody_pitch_class"] == 4
    ][0]

    assert melody_e_entry["occurrence_count"] == 3

    assert melody_e_entry["example_measure"] == 1


# ---------------------------------------------------------
# analyze_chord_for_tuning -- real Open G data
# ---------------------------------------------------------

def test_analyze_chord_for_tuning_real_data():

    service = _service()

    entry = {
        "root_pc": 0,
        "quality_code": "",
        "symbol": "C",
        "melody_pitch_class": 4,
        "melody_midi": 64,
        "occurrence_count": 1,
        "example_measure": 1,
    }

    result = analyze_chord_for_tuning(service, OPEN_G, entry)

    assert result.root == "C"

    assert result.quality_display == "Major"

    assert result.melody_note == "E4"

    assert result.usable_shape_count > 0

    assert result.selected_shape.shape == "2012"

    assert result.realization_tier == "DIRECT_REALIZATION"


def test_analyze_chord_for_tuning_no_melody_note():

    service = _service()

    entry = {
        "root_pc": 0,
        "quality_code": "",
        "symbol": "C",
        "melody_pitch_class": None,
        "melody_midi": None,
        "occurrence_count": 1,
        "example_measure": 1,
    }

    result = analyze_chord_for_tuning(service, OPEN_G, entry)

    assert result.melody_note is None

    assert result.realization_tier == ""

    # Still picks a shape (the top of get_shapes()) even with
    # no melody note to evaluate against.
    assert result.selected_shape is not None


def test_analyze_chord_for_tuning_unrecognized_quality():

    service = _service()

    entry = {
        "root_pc": 0,
        "quality_code": "totally_unknown",
        "symbol": "C???",
        "melody_pitch_class": None,
        "melody_midi": None,
        "occurrence_count": 1,
        "example_measure": 1,
    }

    result = analyze_chord_for_tuning(service, OPEN_G, entry)

    assert result.quality_display is None

    assert result.usable_shape_count == 0

    assert result.selected_shape is None


# ---------------------------------------------------------
# analyze_score_for_tuning -- real My Favorite Things file,
# the actual aDADE vs aEADE comparison this task exists for
# ---------------------------------------------------------

def test_real_aureolin_stand_in_comparison():
    """
    No Aureolin file has been provided. This uses the real
    My Favorite Things file (which genuinely is aDADE-vs-aEADE
    comparable, since both are named tunings for E minor
    material) as the closest available real-data stand-in,
    validating the analysis machinery end to end against real
    data -- ready to point at Aureolin once it exists. Skips
    gracefully if the file isn't present locally.
    """

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

    service = _service()

    a_dade = get_tunings()["Double D"]  # aDADE

    a_eade = get_tunings()["A Modal Sawmill"]  # aEADE

    analysis_dade = analyze_score_for_tuning(
        p.score, a_dade, service
    )

    analysis_eade = analyze_score_for_tuning(
        p.score, a_eade, service
    )

    assert analysis_dade.tuning_symbol == "aDADE"

    assert analysis_eade.tuning_symbol == "aEADE"

    assert len(analysis_dade.occurrences) > 0

    assert len(analysis_dade.occurrences) == len(
        analysis_eade.occurrences
    )

    # Confirmed, real finding from this exact comparison: the
    # two tunings tie on tier/quality/count metrics, but differ
    # in which specific shape gets selected for several chords.
    # This test locks in that the machinery can actually detect
    # such a difference when the aggregate counts alone can't.
    differing_shapes = [
        (od.chord_symbol, od.selected_shape.shape, oe.selected_shape.shape)
        for od, oe in zip(
            analysis_dade.occurrences, analysis_eade.occurrences
        )
        if od.selected_shape and oe.selected_shape
        and od.selected_shape.shape != oe.selected_shape.shape
    ]

    assert len(differing_shapes) > 0, (
        "expected at least one chord where aDADE and aEADE "
        "select genuinely different shapes"
    )
