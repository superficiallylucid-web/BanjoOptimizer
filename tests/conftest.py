import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


sys.path.insert(
    0,
    str(PROJECT_ROOT)
)


# ---------------------------------------------------------
# Test fixture/output infrastructure (Phase 1).
#
# Root cause this exists to fix: fixture paths were referenced
# via at least three different, incompatible conventions across
# the existing suite before this -- hardcoded "scores/X.mscz"
# literals, a tests/-relative TEST_FOLDER.glob() lookup (test_
# music.py's own find_score_file()), and bare filenames resolved
# against whatever the current working directory happened to be
# (e.g. test_bo36_chord_corridor.py's own FULL_SONG_PATH,
# confirmed to require the fixture living directly in the
# project ROOT, not scores/ at all). This produced repeated,
# real confusion: tests passing or failing depending on which
# directory pytest was invoked from, and on which of several
# scattered copies of a given fixture happened to exist locally.
#
# Phase 1 establishes ONE canonical location and lookup function
# for TEST fixtures (test_scores/, via fixture_path() below) and
# ONE canonical mechanism for TEST-generated output (test_output/,
# via new_output_dir() below) -- deliberately separate from
# the application's own real scores/ and output/ directories, so
# running the suite can never read stale application inputs or
# write into, and pollute, real application output.
#
# This is a proof-of-concept covering ~5-10 representative tests
# (see BO-149 Phase 1 delivery report) -- the remaining suite
# still uses its own prior, inconsistent conventions and has NOT
# been migrated yet. Do not assume every test in this suite uses
# fixture_path()/new_output_dir() until Phase 2 completes.
# ---------------------------------------------------------

TEST_SCORES_DIR = PROJECT_ROOT / "test_scores"

TEST_OUTPUT_DIR = PROJECT_ROOT / "test_output"


def fixture_path(filename):
    """
    The single canonical way for a test to obtain the path to a
    test-input .mscz fixture: by filename, resolved against
    test_scores/ -- and ONLY test_scores/. Deliberately does not
    fall back to scores/, the project root, or anywhere else: a
    silent fallback would just reproduce the exact "which of
    several scattered copies did this actually load" confusion
    this mechanism exists to eliminate.

    Returns a pathlib.Path. Raises FileNotFoundError, naming the
    exact canonical location expected, if the fixture is not
    present there -- fixture lookup failures should be loud and
    immediately actionable, never a downstream MuseScoreFile
    parse error whose real cause is "wrong directory."

    NOT named test_score() or anything else starting with
    test_, on purpose -- confirmed directly (not assumed) that
    pytest's own collection mistakes ANY top-level name starting
    with test_ for a test case the moment a test module imports
    it into its own namespace, even though it's genuinely
    defined in conftest.py (which pytest itself does not
    collect). A first version of this helper named test_score()
    was tried and produced a real collection ERROR ("fixture
    'filename' not found") the instant any test module did
    `from conftest import test_score` -- caught here, before any
    real test file was migrated to use it.
    """

    path = TEST_SCORES_DIR / filename

    if not path.exists():

        raise FileNotFoundError(
            f"Test fixture not found: {filename!r}\n"
            f"Expected at canonical location: {path}\n"
            f"(All test fixtures must live directly in "
            f"test_scores/ -- see conftest.py's own "
            f"fixture_path() docstring for why this does not "
            f"fall back to scores/ or any other location.)"
        )

    return path


def new_output_dir(timestamp=None):
    """
    The single canonical way for a test to obtain a fresh,
    writable output directory for generated files (.mscz output,
    intermediate artifacts, etc) -- always under test_output/,
    never the real application output/ directory.

    Also deliberately NOT named starting with test_ -- same
    pytest-collection hazard as fixture_path() above, confirmed
    the same way.

    Deliberately reuses output.create_run_folder() UNMODIFIED,
    pointed at TEST_OUTPUT_DIR instead of the application's own
    output/ -- create_run_folder() already accepts any
    base_output_folder and has no hardcoded "output" path baked
    into its own body (confirmed directly before writing this),
    so no second, competing output-directory mechanism is
    introduced here; this is the same, single mechanism the real
    application uses, just given a different, test-only root.

    Returns a new, timestamped pathlib.Path (via create_run_
    folder()'s own existing collision-avoidance -- see its own
    docstring), so parallel/repeated test runs never silently
    overwrite a previous run's output. test_output/ itself is
    safe to delete/clear entirely between runs -- nothing outside
    the test suite reads from it.
    """

    from output import create_run_folder

    return create_run_folder(TEST_OUTPUT_DIR, timestamp=timestamp)
