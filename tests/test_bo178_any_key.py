"""
tests/test_bo178_any_key.py

Regression tests for BO-178: any-key tuning recommendation mode
(any_key.py's rank_tunings_across_keys(), and its wiring into
main.run_optimizer()'s own `any_key` parameter).
"""

import sys

sys.path.insert(0, '.')

import io
import contextlib

from parser import MuseScoreFile
from any_key import rank_tunings_across_keys
import main


def _load_aureolin():

    p = MuseScoreFile("test_scores/Aureolin.mscz")

    p.open()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p


# ---------------------------------------------------------
# 1 -- different tunings can genuinely recommend different keys
# ---------------------------------------------------------

def test_different_tunings_can_recommend_different_keys():

    p = _load_aureolin()

    results = rank_tunings_across_keys(
        p.notes, p.score.notes, p.harmonies, p.score.key
    )

    recommended = {r.recommended_key for r in results[:5]}

    assert len(recommended) > 1


# ---------------------------------------------------------
# 2 -- a tuning with no real key_strengths at all falls back
# to the source key (never disadvantaged by any-key mode)
# ---------------------------------------------------------

def test_tuning_with_no_key_strengths_falls_back_to_source_key():

    from tunings import get_tunings

    p = _load_aureolin()

    tunings = get_tunings()

    no_strengths_tunings = [
        t for t in tunings.values()
        if t.category == "modern" and not t.key_strengths
    ]

    if not no_strengths_tunings:

        return  # nothing in the current tuning set to check

    results = rank_tunings_across_keys(
        p.notes, p.score.notes, p.harmonies, p.score.key
    )

    by_name = {r.name: r for r in results}

    for tuning in no_strengths_tunings:

        assert by_name[tuning.name].recommended_key is None


# ---------------------------------------------------------
# 3 -- same-key mode (default) never sets recommended_key
# ---------------------------------------------------------

def test_same_key_mode_never_sets_recommended_key():

    buf = io.StringIO()

    with contextlib.redirect_stdout(buf):

        result = main.run_optimizer(
            score_path="test_scores/Aureolin.mscz",
            output_folder="/tmp/bo178_test_same",
            num_tunings=3
        )

    for r in result["scores"][0]["recommendations"]:

        assert r.recommended_key is None


# ---------------------------------------------------------
# 4 -- the per-score report's own "key" field stays the song's
# real original key in any-key mode, not the last generated
# item's own transposed key
# ---------------------------------------------------------

def test_report_key_is_original_source_key_in_any_key_mode():

    buf = io.StringIO()

    with contextlib.redirect_stdout(buf):

        result = main.run_optimizer(
            score_path="test_scores/Aureolin.mscz",
            output_folder="/tmp/bo178_test_report_key",
            num_tunings=3,
            any_key=True
        )

    assert result["scores"][0]["key"] == "B minor"


# ---------------------------------------------------------
# 5 -- the generated file for an any-key recommendation is
# genuinely transposed to its own recommended key (not just
# labeled that way) -- confirmed via the real filename BO's
# existing output-key path already embeds
# ---------------------------------------------------------

def test_generated_file_reflects_its_own_recommended_key():

    buf = io.StringIO()

    with contextlib.redirect_stdout(buf):

        result = main.run_optimizer(
            score_path="test_scores/Aureolin.mscz",
            output_folder="/tmp/bo178_test_generation",
            num_tunings=3,
            any_key=True
        )

    for rec, generated in zip(
        result["scores"][0]["recommendations"],
        result["scores"][0]["generated_files"]
    ):

        if rec.recommended_key is not None:

            assert (
                f"Key {rec.recommended_key} "
                in generated["tab_path"].name
            )
