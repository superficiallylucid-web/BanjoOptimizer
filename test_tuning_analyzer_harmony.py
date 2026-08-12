"""
tests/test_tuning_analyzer_harmony.py

Minimal tests for TuningAnalyzer's new optional `harmonies`
parameter -- structural plumbing only (see optimizer.py's
__init__ and DESIGN.md). Does not test any Playing Model
integration, since none exists yet.
"""

from pathlib import Path

from parser import MuseScoreFile

from optimizer import TuningAnalyzer

from models import Harmony


TEST_FOLDER = Path(__file__).parent

WHITE_CHRISTMAS_PATH = (
    TEST_FOLDER.parent / "scores"
    / "White Christmas (G (gCGBD)).mscz"
)


def _sample_notes():

    return [
        {"measure": 1, "midi": 67},
        {"measure": 1, "midi": 71},
        {"measure": 2, "midi": 74},
    ]


# ---------------------------------------------------------
# 1 -- TuningAnalyzer(notes, key) still works unchanged
# ---------------------------------------------------------

def test_backward_compatible_two_arg_construction():

    analyzer = TuningAnalyzer(_sample_notes(), "G major")

    assert analyzer.notes == _sample_notes()

    assert analyzer.key == "G major"

    assert analyzer.harmonies == []


# ---------------------------------------------------------
# 2 -- harmony can be supplied
# ---------------------------------------------------------

def test_harmonies_can_be_supplied():

    harmonies = [
        Harmony(
            measure=1, root_pc=7, quality_code="", symbol="G",
            tones=[7, 11, 2], beat=0.0
        )
    ]

    analyzer = TuningAnalyzer(
        _sample_notes(), "G major", harmonies
    )

    assert analyzer.harmonies == harmonies


# ---------------------------------------------------------
# 3 -- supplied harmony is available on the analyzer for a
# future integration step to use
# ---------------------------------------------------------

def test_supplied_harmony_is_stored_as_is_not_reparsed():

    harmony = Harmony(
        measure=5, root_pc=4, quality_code="m7", symbol="Em7",
        tones=[4, 7, 11, 2], beat=1.0
    )

    analyzer = TuningAnalyzer(_sample_notes(), "E minor", [harmony])

    assert analyzer.harmonies[0] is harmony

    assert analyzer.harmonies[0].symbol == "Em7"


# ---------------------------------------------------------
# 4 -- existing production scoring is unchanged whether or
# not harmonies are supplied, and matches the established
# real-score baseline
# ---------------------------------------------------------

def test_score_tuning_unaffected_by_harmonies_argument():

    if not WHITE_CHRISTMAS_PATH.exists():

        print(
            "SKIPPED: White Christmas score not found locally"
        )

        return

    p = MuseScoreFile(WHITE_CHRISTMAS_PATH)

    p.open()
    p.read_title()
    p.read_time_signature()
    staff_used = p.read_melody_notes()
    p.estimate_key()
    p.read_harmonies(staff_used)

    without_harmony = TuningAnalyzer(p.notes, p.key)

    with_harmony = TuningAnalyzer(p.notes, p.key, p.harmonies)

    results_without = without_harmony.analyze()

    results_with = with_harmony.analyze()

    # Same top-3 modern recommendations, same order, same
    # scores -- confirms harmonies has zero effect on scoring.
    top_without = [
        (r.name, r.score) for r in results_without["modern"][:3]
    ]

    top_with = [
        (r.name, r.score) for r in results_with["modern"][:3]
    ]

    assert top_without == top_with

    # Matches the established real baseline for this file.
    assert top_without[0][0] == "Open G"
