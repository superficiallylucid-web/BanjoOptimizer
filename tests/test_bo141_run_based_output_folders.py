"""
tests/test_bo141_run_based_output_folders.py

Focused tests for BO-141: create_run_folder() creates one
timestamped output directory per BO run (no "generated"
subfolder), with a minimal, collision-safe numeric suffix if
the exact timestamp is already taken.

Uses a fixed, injected timestamp throughout -- no dependency on
actual wall-clock time, per this BO's own explicit testing
requirement. A real, end-to-end CLI validation (actual
wall-clock timestamps, two full runs) lives in
test_main_entrypoint_smoke.py's own updated
test_main_py_generates_mscz_files, not duplicated here.
"""

import sys

sys.path.insert(0, '.')

from output import create_run_folder

import tempfile

from pathlib import Path

import shutil


def _temp_base():

    return Path(tempfile.mkdtemp())


# ---------------------------------------------------------
# 1 -- a run creates a timestamped output directory
# ---------------------------------------------------------

def test_creates_timestamped_directory():

    base = _temp_base()

    try:

        run_folder = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        assert run_folder == base / "2026-09-03_190512"

        assert run_folder.exists()

        assert run_folder.is_dir()

    finally:

        shutil.rmtree(base)


# ---------------------------------------------------------
# 2/3/4 -- structure: report and .mscz directly inside, no
# "generated" subfolder at all (verified by simulating what a
# caller would write into the returned folder)
# ---------------------------------------------------------

def test_no_generated_subfolder_is_created():

    base = _temp_base()

    try:

        run_folder = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        assert not (run_folder / "generated").exists()

        assert list(run_folder.iterdir()) == []

    finally:

        shutil.rmtree(base)


def test_report_and_mscz_land_directly_in_run_folder():

    base = _temp_base()

    try:

        run_folder = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        report_path = run_folder / "BanjoOptimizer_report.txt"

        report_path.write_text("test report")

        mscz_path = run_folder / "Song - Tuning - TAB.mscz"

        mscz_path.write_bytes(b"fake mscz content")

        assert report_path.exists()

        assert mscz_path.exists()

        assert report_path.parent == mscz_path.parent == (
            run_folder
        )

    finally:

        shutil.rmtree(base)


# ---------------------------------------------------------
# 5 -- two runs produce two distinct directories, neither
# overwrites the other
# ---------------------------------------------------------

def test_two_different_timestamps_produce_distinct_folders():

    base = _temp_base()

    try:

        run_1 = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        run_2 = create_run_folder(
            base, timestamp="2026-09-03_191047"
        )

        assert run_1 != run_2

        assert run_1.exists() and run_2.exists()

    finally:

        shutil.rmtree(base)


# ---------------------------------------------------------
# 8 -- collision handling: same timestamp requested twice gets
# a minimal numeric suffix, never silently reuses the existing
# directory
# ---------------------------------------------------------

def test_same_timestamp_collision_gets_numeric_suffix():

    base = _temp_base()

    try:

        run_1 = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        run_2 = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        assert run_1 != run_2, (
            "Expected a genuine collision to produce two "
            "distinct directories, not silently reuse the "
            "first one."
        )

        assert run_2.name == "2026-09-03_190512_1"

        assert run_1.exists() and run_2.exists()

    finally:

        shutil.rmtree(base)


def test_multiple_collisions_increment_suffix():

    base = _temp_base()

    try:

        run_1 = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        run_2 = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        run_3 = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        assert run_2.name == "2026-09-03_190512_1"

        assert run_3.name == "2026-09-03_190512_2"

        assert len({run_1, run_2, run_3}) == 3

    finally:

        shutil.rmtree(base)


# ---------------------------------------------------------
# base_output_folder itself is created if it doesn't exist
# ---------------------------------------------------------

def test_base_output_folder_created_if_missing():

    base = _temp_base() / "does_not_exist_yet"

    try:

        run_folder = create_run_folder(
            base, timestamp="2026-09-03_190512"
        )

        assert base.exists()

        assert run_folder.exists()

    finally:

        shutil.rmtree(base.parent)


# ---------------------------------------------------------
# no-timestamp default uses real wall-clock time (format only
# check -- not asserting an exact value, since real time is
# involved here specifically)
# ---------------------------------------------------------

def test_default_timestamp_matches_expected_format():

    import re

    base = _temp_base()

    try:

        run_folder = create_run_folder(base)

        assert re.match(
            r"^\d{4}-\d{2}-\d{2}_\d{6}$", run_folder.name
        ), (
            f"Expected the default (real wall-clock) timestamp "
            f"to match YYYY-MM-DD_HHMMSS, got "
            f"{run_folder.name!r}."
        )

    finally:

        shutil.rmtree(base)
