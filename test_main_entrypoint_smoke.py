"""
tests/test_main_entrypoint_smoke.py

Regression test for the exact class of failure reported after
BO-12: `python main.py` failed at startup with an ImportError
(main.py -> optimizer.py -> playing_model.py ->
melody_box_analysis.py -> music.py), even though every existing
test in this suite passed.

Why the existing suite didn't catch it: every other test file
imports specific modules/functions directly (e.g. `from
optimizer import TuningAnalyzer`) within a sandbox that already
had every file BO-12 depends on. None of them actually ran
main.py itself, as a script, from a fresh process -- which is
the only way to genuinely catch a broken import chain at the
real entry point. This test does exactly that.
"""

import subprocess

import sys

from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def test_main_py_starts_without_import_error():
    """
    Runs `python main.py` as a real subprocess (not an import
    inside this test process, which would share this process's
    already-successful import state) and confirms it doesn't
    fail with an ImportError/ModuleNotFoundError during startup.
    Doesn't require any score files to be present -- main.py
    handles "no files found" gracefully; this test only cares
    that the import chain itself resolves.
    """

    result = subprocess.run(
        [sys.executable, "main.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60
    )

    combined_output = result.stdout + result.stderr

    assert "ImportError" not in combined_output, (
        f"main.py failed to start:\n{combined_output}"
    )

    assert "ModuleNotFoundError" not in combined_output, (
        f"main.py failed to start:\n{combined_output}"
    )

    assert "Traceback" not in combined_output, (
        f"main.py raised an unexpected exception:\n"
        f"{combined_output}"
    )


def test_full_import_chain_resolves():
    """
    A faster, in-process companion to the subprocess test above:
    directly imports every LIBRARY module in the reported
    failure chain, in order, so a broken link is attributed
    precisely rather than just "main.py crashed somewhere."

    Does NOT import main.py itself here -- main.py has top-
    level executing code (no `if __name__ == "__main__"` guard),
    so importing it would run the whole app as a side effect of
    this test; the subprocess test above is the correct way to
    exercise main.py itself.
    """

    import music

    import melody_box_analysis

    import playing_model

    import optimizer

    assert hasattr(music, "quality_code_to_display_name")

    assert callable(music.quality_code_to_display_name)
