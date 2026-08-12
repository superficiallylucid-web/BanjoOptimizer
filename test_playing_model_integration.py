"""
tests/test_playing_model_integration.py

Tests for the Playing Model's integration into production
tuning scoring (TuningAnalyzer.playing_model_bonus() and its
wiring into score_tuning()) -- BO-12. Does not test the Playing
Model's internal heuristics themselves (see
test_playing_model.py); these confirm the INTEGRATION is small,
conditional, and non-disruptive, per the task's own constraint
not to tune the model's weights in this step.
"""

from pathlib import Path

from parser import MuseScoreFile

from optimizer import TuningAnalyzer

from tunings import get_tunings


TEST_FOLDER = Path(__file__).parent

WHITE_CHRISTMAS_PATH = (
    TEST_FOLDER.parent / "scores"
    / "White Christmas (G (gCGBD)).mscz"
)

MFT_PATH = (
    TEST_FOLDER.parent / "My_Favorite_Things__Em__aEADE__.mscz"
)

AUREOLIN_PATH = (
    TEST_FOLDER.parent / "Aureolin__Bm__aEADE__.mscz"
)


def _load(path, staff=None):

    p = MuseScoreFile(path)

    p.open()
    p.read_title()
    p.read_time_signature()
    used_staff = p.read_melody_notes()
    p.estimate_key()
    p.read_harmonies(staff if staff is not None else used_staff)

    return p


# ---------------------------------------------------------
# 1 -- a tuning can receive a Playing Model contribution when
# harmony (and melody_notes) is present
# ---------------------------------------------------------

def test_contribution_present_with_full_context():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p = _load(WHITE_CHRISTMAS_PATH)

    analyzer = TuningAnalyzer(
        p.notes, p.key, p.harmonies, p.score.notes
    )

    open_g = get_tunings()["Open G"]

    bonus = analyzer.playing_model_bonus(open_g)

    assert bonus != 0.0


# ---------------------------------------------------------
# 2 -- a score without harmony still works (zero contribution,
# no error)
# ---------------------------------------------------------

def test_zero_contribution_without_harmony():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p = _load(WHITE_CHRISTMAS_PATH)

    analyzer = TuningAnalyzer(p.notes, p.key)  # legacy 2-arg

    open_g = get_tunings()["Open G"]

    assert analyzer.playing_model_bonus(open_g) == 0.0

    # And the full pipeline still runs and produces a result.
    results = analyzer.analyze()

    assert results["modern"][0].name == "Open G"


# ---------------------------------------------------------
# 3 -- the contribution is small relative to the existing
# tuning score
# ---------------------------------------------------------

def test_contribution_is_small_relative_to_existing_score():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p = _load(WHITE_CHRISTMAS_PATH)

    without_harmony = TuningAnalyzer(p.notes, p.key)

    with_harmony = TuningAnalyzer(
        p.notes, p.key, p.harmonies, p.score.notes
    )

    base_result = without_harmony.analyze()["modern"][0]

    full_result = with_harmony.analyze()["modern"][0]

    assert base_result.name == full_result.name

    contribution = full_result.score - base_result.score

    # Deliberately small and conservative: less than 10% of the
    # base score, on the real test scores this was checked
    # against.
    assert 0 < contribution < base_result.score * 0.10


# ---------------------------------------------------------
# 4 -- existing score components have not changed (the
# playing_model_bonus() call is additive, not a replacement)
# ---------------------------------------------------------

def test_existing_score_components_unchanged():

    if not WHITE_CHRISTMAS_PATH.exists():

        print("SKIPPED: White Christmas score not found locally")

        return

    p = _load(WHITE_CHRISTMAS_PATH)

    analyzer = TuningAnalyzer(p.notes, p.key)  # legacy path

    result = analyzer.analyze()["modern"][0]

    # Matches the exact pre-BO-12 established baseline for this
    # file -- confirms no existing weight/component changed.
    assert result.name == "Open G"

    assert result.score == 123.38


# ---------------------------------------------------------
# 5 -- final recommendation ranking remains sensible (matches
# established baselines) for all three real test scores
# ---------------------------------------------------------

def test_ranking_unchanged_for_real_scores():

    cases = [
        (WHITE_CHRISTMAS_PATH, None, ["Open G", "C Standard", "G Modal Sawmill"]),
        (MFT_PATH, 4, ["A Modal Sawmill", "Old G", "Open G"]),
        (AUREOLIN_PATH, 4, ["Double D", "Open G", "C Standard"]),
    ]

    for path, staff, expected_top3 in cases:

        if not path.exists():

            print(f"SKIPPED: {path.name} not found locally")

            continue

        p = _load(path, staff)

        analyzer = TuningAnalyzer(
            p.notes, p.key, p.harmonies, p.score.notes
        )

        top3 = [r.name for r in analyzer.analyze()["modern"][:3]]

        assert top3 == expected_top3, (
            f"{path.name}: expected {expected_top3}, got {top3}"
        )
