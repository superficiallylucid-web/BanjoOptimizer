import datetime


def clear_output():
    with open("optimizer_log.txt", "w", encoding="utf-8") as f:
        f.write("")


def output(*args):
    text = " ".join(str(arg) for arg in args)

    print(text)

    with open("optimizer_log.txt", "a", encoding="utf-8") as f:
        f.write(text + "\n")


def create_run_folder(base_output_folder, timestamp=None):
    """
    BO-141 -- create and return the path to one, new, timestamped
    run directory (base_output_folder / "YYYY-MM-DD_HHMMSS"),
    creating base_output_folder itself first if it doesn't
    already exist.

    timestamp: injectable, for deterministic tests -- a real
    run always calls this with the default (None), which uses
    the real, current wall-clock time
    (datetime.datetime.now()); a test can instead pass a fixed,
    known string directly, avoiding any dependency on actual
    wall-clock time.

    Collision handling: if the exact timestamped directory
    already exists (e.g. two runs within the same second), a
    minimal numeric suffix ("_1", "_2", ...) is appended and
    retried until a genuinely new, not-yet-existing directory
    is found. Never reuses an existing run directory -- doing
    so would silently recreate the exact overwrite problem this
    exists to solve.
    """

    base_output_folder.mkdir(exist_ok=True)

    if timestamp is None:

        timestamp = datetime.datetime.now().strftime(
            "%Y-%m-%d_%H%M%S"
        )

    candidate = base_output_folder / timestamp

    suffix = 0

    while candidate.exists():

        suffix += 1

        candidate = base_output_folder / f"{timestamp}_{suffix}"

    candidate.mkdir()

    return candidate