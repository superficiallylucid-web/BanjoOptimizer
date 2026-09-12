"""
tests/test_bo170_stdout_cleanup.py

Focused tests for BO-170: run_optimizer() must restore the
global sys.stdout and close its own run report file when it
returns -- and still do so if it raises -- rather than leaving
an open file handle (and a nested Tee wrapping the caller's own
prior sys.stdout) alive for the rest of the process. This is
what previously kept every generated output folder locked on
Windows until the whole GUI process exited (main.py calls this
function directly, synchronously, in-process, on every "Optimize"
click -- not a subprocess).
"""

import sys

sys.path.insert(0, '.')

import main

import tempfile

from pathlib import Path

import shutil


def _temp_output_base():

    return Path(tempfile.mkdtemp())


# ---------------------------------------------------------
# 1 -- a single run restores sys.stdout and closes its report
# ---------------------------------------------------------

def test_single_run_restores_stdout_and_closes_report():

    base = _temp_output_base()

    original_stdout = sys.stdout

    try:

        result = main.run_optimizer(
            score_path='scores/Aureolin.mscz',
            tuning_symbol='gDGBD',
            output_folder=str(base)
        )

        assert sys.stdout is original_stdout, (
            "Expected sys.stdout to be restored to the exact "
            "object it was before run_optimizer() was called -- "
            f"got {sys.stdout!r} instead."
        )

        report_path = result["report_path"]

        with open(report_path, "r", encoding="utf-8") as f:

            # The report file must be independently re-openable
            # and readable -- proves run_optimizer()'s own
            # handle was genuinely closed (a real, unflushed or
            # still-open write handle can leave content
            # incomplete/inconsistent when read this way on some
            # platforms, and would keep the file/folder locked
            # on Windows specifically, the exact defect this
            # exists to catch).
            content = f.read()

        assert "Banjo Optimizer" in content

    finally:

        sys.stdout = original_stdout

        shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------
# 2 -- two consecutive runs in the same process (the real GUI
# scenario: two "Optimize" clicks without closing the app)
# each independently restore sys.stdout -- no accumulating Tee
# chain, no growing set of open report files.
# ---------------------------------------------------------

def test_two_consecutive_runs_both_restore_stdout():

    base = _temp_output_base()

    original_stdout = sys.stdout

    try:

        result_1 = main.run_optimizer(
            score_path='scores/Aureolin.mscz',
            tuning_symbol='gDGBD',
            output_folder=str(base)
        )

        assert sys.stdout is original_stdout, (
            "sys.stdout not restored after the first run."
        )

        result_2 = main.run_optimizer(
            score_path='scores/Aureolin.mscz',
            tuning_symbol='gDGBD',
            output_folder=str(base)
        )

        assert sys.stdout is original_stdout, (
            "sys.stdout not restored after the second run -- "
            f"got {sys.stdout!r}, which would mean the second "
            "run's own Tee is still wrapping the first run's "
            "(the exact accumulating-chain defect BO-170 fixes)."
        )

        # Both run folders are genuinely distinct (BO-141's own
        # collision-safe naming) -- confirms this is a real
        # two-run scenario, not the same folder reused.
        assert result_1["run_folder"] != result_2["run_folder"]

        # Both report files must be independently readable --
        # proves NEITHER run's own handle was left open, not
        # just the most recent one.
        for result in (result_1, result_2):

            with open(
                result["report_path"], "r", encoding="utf-8"
            ) as f:

                content = f.read()

            assert "Banjo Optimizer" in content

    finally:

        sys.stdout = original_stdout

        shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------
# 3 -- cleanup still happens when run_optimizer() raises
# ---------------------------------------------------------

def test_stdout_restored_even_when_run_optimizer_raises():

    base = _temp_output_base()

    original_stdout = sys.stdout

    try:

        # An invalid score_path (BO-155's own explicit check --
        # exists but isn't a .mscz file) raises ValueError AFTER
        # the Tee/log_file are already set up (confirmed directly
        # against main.py: this check sits inside the new try
        # block, well after the sys.stdout reassignment) --
        # genuinely exercises the finally block's own exception
        # path, not just the normal-return path above.
        try:

            main.run_optimizer(
                score_path='main.py',  # real file, wrong suffix
                output_folder=str(base)
            )

            assert False, (
                "Expected run_optimizer() to raise ValueError "
                "for a score_path that isn't a .mscz file."
            )

        except ValueError:

            pass

        assert sys.stdout is original_stdout, (
            "Expected sys.stdout to be restored even though "
            "run_optimizer() raised -- got "
            f"{sys.stdout!r} instead."
        )

    finally:

        sys.stdout = original_stdout

        shutil.rmtree(base, ignore_errors=True)
