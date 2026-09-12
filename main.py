from pathlib import Path
import sys
import os
import argparse
import json

from output import output, clear_output, create_run_folder

from parser import MuseScoreFile
from optimizer import TuningAnalyzer
from recommendations import (
    apply_shared_features, apply_confidence,
    select_additional_strong_alternatives
)
from score_generator import generate_tab_from_template
from tunings import get_tunings
from chord_service import ChordService
from chord_library import ChordLibrary
from models import Tuning

VERSION = "1.0"
# ---------------------------------------------------------
# BO-130 -- command-line options for requesting a specific
# OPEN tuning directly, bypassing the optimizer's own ranking,
# and for narrowing which score in the scores folder to
# process.
#
# --tuning takes the OPEN (un-capo'd) tuning symbol (e.g.
# "gDGBD") -- what the player's strings sound with no capo on
# at all. --capo (optional, defaults to 0/none) shifts strings
# 1-4 of that open tuning by the given number of semitones,
# NEVER the 5th string (confirmed directly, real-world fact) --
# the result is the SOUNDED tuning: what the strings actually
# produce with the capo on, which is what chord-shape/FD
# generation genuinely needs to use, since that's the real,
# physical instrument being played.
#
# --score is independent of the tuning options; it can be used
# alone (narrow to one file, still let the optimizer rank
# tunings normally) or together with --tuning (narrow to one
# file AND skip ranking for it).
# ---------------------------------------------------------

NOTE_NAME_TO_BASE_PITCH_CLASS = {
    "C": 0, "D": 2, "E": 4, "F": 5,
    "G": 7, "A": 9, "B": 11
}

PITCH_CLASS_TO_NOTE_NAME = [
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B"
]

# Confirmed against every one of the 13 built-in tunings'
# own real notes (tunings.get_tunings()) -- the typical octave
# range used at each string position (5th string, then strings
# 1-4), so a symbol parsed from --tuning lands in the same
# practical register as every existing tuning, not an arbitrary
# octave.
TUNING_SYMBOL_STRING_RANGES = [
    (64, 69), (45, 52), (52, 57), (56, 62), (59, 64)
]


def _parse_tuning_symbol(symbol):
    """
    Parse a tuning symbol (e.g. "aFCEG", "gDGBbD", "f#DADD") into
    5 real MIDI notes: 5th string first, then strings 1-4 --
    matching tunings.py's own notes ordering exactly. Validated
    directly against all 13 built-in tunings' own real symbols
    (round-trips exactly, including sharps, a flat ("Bb"), and a
    sharp on the 5th string itself ("f#")) before this function
    was written into main.py.

    The 5th string is always the first character, never carrying
    a flat (no existing tuning uses one there); strings 1-4 may
    each carry a trailing '#' (sharp) or lowercase 'b' (flat).
    """

    tokens = []

    i = 0

    letter = symbol[0].upper()

    accidental = 0

    i = 1

    if i < len(symbol) and symbol[i] == "#":

        accidental = 1

        i += 1

    tokens.append((letter, accidental))

    while i < len(symbol):

        letter = symbol[i].upper()

        i += 1

        accidental = 0

        if i < len(symbol) and symbol[i] == "#":

            accidental = 1

            i += 1

        elif i < len(symbol) and symbol[i] == "b":

            accidental = -1

            i += 1

        tokens.append((letter, accidental))

    if len(tokens) != 5:

        return None

    notes = []

    for (letter, accidental), (lo, hi) in zip(
        tokens, TUNING_SYMBOL_STRING_RANGES
    ):

        if letter not in NOTE_NAME_TO_BASE_PITCH_CLASS:

            return None

        pitch_class = (
            NOTE_NAME_TO_BASE_PITCH_CLASS[letter] + accidental
        ) % 12

        placed = None

        for octave_base in range(0, 132, 12):

            candidate = octave_base + pitch_class

            if lo <= candidate <= hi:

                placed = candidate

                break

        if placed is None:

            placed = (
                min(
                    range(0, 132),
                    key=lambda m: (
                        max(lo - m, m - hi, 0)
                        if m % 12 == pitch_class else 9999
                    )
                )
            )

        notes.append(placed)

    return notes


def _notes_to_symbol(notes):
    """
    The reverse of _parse_tuning_symbol(): given 5 real MIDI
    notes (5th string first, then strings 1-4), build the
    symbol string (e.g. [69, 53, 60, 64, 67] -> "aFCEG").
    Always uses sharps, never flats (matching every one of the
    13 built-in tunings' own symbols except the one deliberate
    "Bb" -- a sharp-only reverse mapping is unambiguous and
    matches the overwhelming existing convention).
    """

    fifth_name = PITCH_CLASS_TO_NOTE_NAME[notes[0] % 12].lower()

    rest = "".join(
        PITCH_CLASS_TO_NOTE_NAME[n % 12] for n in notes[1:]
    )

    return fifth_name + rest


def resolve_project_folder():
    """
    BO-160 -- factored out of run_optimizer() (where this exact
    sys.frozen logic previously lived inline, added back in
    BO-153) so it can also be called before any optimization run
    happens at all. Specifically needed by the GUI's own Settings
    dialog (BO-160), which has to resolve this same path to
    find/write the settings file -- independent of, and prior to,
    ever calling run_optimizer() itself. run_optimizer()'s own
    project_folder parameter is unchanged; when not given
    explicitly, it now simply calls this instead of repeating the
    same three lines inline.
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    return Path(__file__).parent


def _settings_path(project_folder):
    return project_folder / "banjo_optimizer_settings.json"


def load_settings(project_folder=None):
    """
    BO-160 -- returns the saved settings dict (currently just
    "scores_folder" / "output_folder", each an optional string
    path), or an empty dict if no settings file exists yet, or if
    it exists but is genuinely unreadable/corrupted. Deliberately
    never raises: a missing or bad settings file should never be
    able to prevent the app from starting or running -- it should
    just behave as though nothing was ever configured, falling
    back to this application's existing, ordinary defaults.
    """

    if project_folder is None:
        project_folder = resolve_project_folder()

    path = _settings_path(project_folder)

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}


def save_settings(settings, project_folder=None):
    """
    BO-160 -- writes the given dict as the saved settings file,
    replacing it outright (not merged with whatever was there
    before -- the caller, the GUI's own Settings dialog, is
    responsible for including every key it wants kept, same as
    every other file-writing convention already used throughout
    this codebase: no silent partial updates).
    """

    if project_folder is None:
        project_folder = resolve_project_folder()

    path = _settings_path(project_folder)

    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def compute_sounded_tuning(tuning_symbol, capo=None, fifth_string=None):
    """
    BO-165 -- extracted from run_optimizer()'s own REQUESTED_TUNING
    construction (BO-163), where this exact logic previously lived
    inline. Factored out, with zero behavior change (confirmed via
    byte-identical CLI verification during this change), so it can
    be called independently of run_optimizer() itself -- which
    requires a real score file and runs the full analysis/scoring
    pipeline, making it unusable for a lightweight GUI live-preview
    (BO-165's own "sounded tuning" display) that needs to update on
    every capo/5th-string change with no score involved at all.

    Returns (sounded_notes, sounded_symbol, capo_value) -- the same
    three pieces run_optimizer() itself needs to build its
    REQUESTED_TUNING (below); capo_value is capo if given, else 0
    (same default run_optimizer() always used).

    Raises ValueError on an unparseable tuning_symbol or
    fifth_string, or a capo outside 1-5 -- identical error
    conditions/messages run_optimizer() itself always raised
    for these, since this function now IS that logic.
    """

    _open_notes = _parse_tuning_symbol(tuning_symbol)

    if _open_notes is None:

        raise ValueError(
            f"Could not parse --tuning {tuning_symbol!r} -- "
            f"expected a 5-character-ish symbol like 'gDGBD' "
            f"(5th string, then strings 1-4, each optionally "
            f"followed by '#' or 'b')."
        )

    if capo is not None and not (1 <= capo <= 5):

        raise ValueError("--capo must be between 1 and 5.")

    _capo_value = capo if capo is not None else 0

    # Capo shifts strings 1-4 ONLY (indices 1-4 of notes) --
    # never the 5th string (index 0), confirmed directly as a
    # real-world, physical fact earlier in this project.
    _sounded_notes = [_open_notes[0]] + [
        note + _capo_value for note in _open_notes[1:]
    ]

    # BO-163 -- fifth_string: an independent 5th-string
    # override, applied on top of the capo-only shift above.
    # Reuses _parse_tuning_symbol() itself for the letter-to-
    # pitch parsing (not a duplicate parser): a 5-character
    # symbol is built where only the first character (the
    # 5th-string token the caller actually gave) matters --
    # the trailing "CGCD" is arbitrary, known-valid padding
    # (Double C's own real strings 1-4) purely because
    # _parse_tuning_symbol() always parses all 5 tokens
    # together; only its result's index 0 is ever used here.
    if fifth_string is not None:

        _fifth_string_notes = _parse_tuning_symbol(
            fifth_string + "CGCD"
        )

        if _fifth_string_notes is None:

            raise ValueError(
                f"Could not parse 5th string "
                f"{fifth_string!r} -- expected a single note "
                f"letter like 'A' or 'F#'."
            )

        _sounded_notes[0] = _fifth_string_notes[0]

    _sounded_symbol = _notes_to_symbol(_sounded_notes)

    return _sounded_notes, _sounded_symbol, _capo_value


def run_optimizer(
    score_filename=None, score_path=None, tuning_symbol=None,
    capo=None, alternatives=0, num_tunings=3, project_folder=None,
    scores_folder=None, output_folder=None, fifth_string=None
):
    """
    BO-153 -- the application's real entry point, extracted from
    what was previously module-level script code that ran
    unconditionally on import (main.py had no run_optimizer()/
    __main__ separation at all before this -- confirmed directly,
    the entire pipeline from argument handling through file
    generation executed the instant `import main` ran, which is
    incompatible with anything -- a GUI included -- that wants to
    import this module without immediately running a full
    optimization pass against sys.argv).

    This function contains the EXACT same logic previously at
    module level, moved here with no behavior changes beyond two
    deliberate ones:

    1. Every prior `print(...); sys.exit(1)` validation failure
       (bad --tuning symbol, --capo out of range, --capo without
       --tuning, unknown --score filename) now raises ValueError
       with the identical message text instead, so a caller (CLI
       wrapper below, or a future GUI) decides how to surface the
       failure rather than the process exiting out from under it.
    2. A structured result is now returned (see below), built
       alongside -- not instead of -- the existing output()/print
       calls, which are all still present, unchanged, and still
       produce the exact same console/report-file text as before
       (confirmed via byte-for-byte diff against pre-refactor
       output during this change's own verification).

    project_folder: injectable for tests/GUI; defaults to the
    same sys.frozen/__file__-based resolution the CLI always
    used.

    BO-155 -- score_path (new): an absolute path to a .mscz file
    anywhere on disk, bypassing the scores/-folder lookup
    entirely. Added for the GUI's own real file picker (BO-155),
    which needs to open a score wherever the user actually put
    it, not only ones already copied into the application's own
    scores/ folder. Purely additive: score_filename's existing
    behavior (matching a file already inside scores/, by name --
    what the CLI's own --score has always done) is completely
    unchanged when score_path is not given, which is the only
    way the CLI itself ever calls this function. If both are
    given, score_path wins (score_filename is ignored) -- no
    real caller does this today, but a defined precedence is
    better than an ambiguous one.

    BO-157 -- num_tunings (new): how many of the top-ranked
    "modern" tunings to return/generate unconditionally --
    previously a hardcoded 3, now parameterized so the GUI can
    offer a single "Number of tunings" control (replacing its
    former separate checkbox+count for a genuinely different
    mechanism -- see below). Defaults to 3, preserving the exact
    prior hardcoded behavior for the CLI, which never exposed a
    way to change this and still doesn't. Deliberately distinct
    from the alternatives parameter below: num_tunings always
    returns exactly that many results, unconditionally, straight
    off the ranked list -- it does not apply the stricter
    still-qualifies-as-strong test (combined_score > 0) that
    alternatives/select_additional_strong_alternatives() uses for
    rank-4+ candidates. The GUI (BO-157) no longer calls
    alternatives at all (its own checkbox+spinner for that was
    removed in favor of num_tunings), but alternatives itself is
    untouched here and still fully available to CLI callers via
    --alternatives.

    BO-160 -- scores_folder / output_folder (new): explicit,
    per-call overrides for where input scores are looked up and
    where generated output is written, taking precedence over any
    saved default (see load_settings() above) when given, which
    in turn takes precedence over the plain
    project_folder/scores and project_folder/output this
    application always fell back to before BO-160. This
    resolution order (explicit call > saved setting > original
    hardcoded default) is deliberately the same shape
    project_folder itself already used. The CLI's own new
    --scores-folder/--output-folder flags (BO-160) are one-off
    overrides only, same as --score always was -- they do not
    themselves save anything; saving a new default only happens
    via the GUI's own Settings dialog calling save_settings()
    directly.

    BO-163 -- fifth_string (new): an independent, explicit
    override for the 5th string's sounded pitch when tuning_symbol
    is also given, only meaningful alongside a specific tuning
    (same requirement shape as capo -- ignored/irrelevant without
    tuning_symbol, since there is no "requested tuning" for it to
    apply to). None (the default) means genuinely unchanged: the
    5th string keeps the base tuning's own open pitch regardless
    of capo, matching this function's prior, only behavior.
    Deliberately NOT derived from capo by any formula (e.g. NOT
    "base 5th + capo") -- confirmed directly, during this
    feature's own investigation, against three real reference
    tunings that a capo-based formula cannot reproduce:
        Double C + capo 2 + 5th "A"  -> aDADE (matches the real,
            named "Double D" built-in tuning exactly)
        C Standard + capo 5 + 5th "A" -> aFCEG (naively shifting
            C Standard's own open 5th, g, by capo 5 would give
            "C", not "A" -- proving no formula linking the two)
        Open G + capo 3 + 5th "F" -> fFBbDF (the 5th string here
            is LOWERED from the base's own open g to f -- a
            capo can only ever raise a pitch, so this result is
            only reachable by treating the 5th string as fully
            independent)
    Reuses _parse_tuning_symbol() itself for the actual letter-to-
    pitch parsing (not a duplicate parser) -- see the inline
    comment where it's used, below, for exactly how.

    Returns a dict:
        {
            "run_folder": Path,
            "report_path": Path,
            "scores": [
                {
                    "filename": str,
                    "title": str,
                    "key": str,
                    "time_signature": str,
                    "total_notes": int,
                    "staff_used": int,
                    "requested_tuning": Tuning or None,
                    "recommendations": [TuningResult, ...],
                    "additional_alternatives": [TuningResult, ...],
                    "generated_files": [
                        {
                            "tuning_name": str,
                            "tab_path": Path or None,
                            "tab_shapes_applied": int or None,
                            "tab_shapes_skipped": int or None,
                            "melody_exceptions": [...],
                            "error": str or None,
                        },
                        ...
                    ],
                },
                ...
            ],
        }

    Raises ValueError on any of the same invalid-input cases the
    CLI previously exited on directly (see above) -- the caller
    is responsible for deciding what to do (the __main__ block
    below preserves the exact prior CLI behavior: print the
    message, exit 1).

    Known limitation, not addressed by this refactor: this
    function still redirects sys.stdout (via Tee, below) to also
    write the run's report file, same as the CLI always did. A
    future GUI caller running this on a background thread, or
    wanting to avoid a global sys.stdout mutation, would need
    this addressed separately -- flagged here rather than solved,
    since solving it isn't needed for the CLI to keep working
    exactly as it always has, and doing so blind (without a real
    GUI caller to verify against) risks guessing wrong about what
    that caller actually needs.
    """

    clear_output()

    all_scores_results = []

    REQUESTED_TUNING = None

    if tuning_symbol is not None:

        # BO-165 -- this entire block's own computation now lives
        # in compute_sounded_tuning() (above), called here instead
        # of duplicated inline. Zero behavior change (confirmed via
        # byte-identical CLI verification) -- this is a pure
        # extraction, not a new code path.
        _sounded_notes, _sounded_symbol, _capo_value = (
            compute_sounded_tuning(tuning_symbol, capo, fifth_string)
        )

        # name includes the capo value (when given) so the generated
        # filename (built elsewhere from tuning.name and tuning.
        # symbol) is genuinely unique per capo value -- confirmed
        # real, not merely cosmetic: without this, different --capo
        # values for the same --tuning silently overwrote each
        # other's output file.
        REQUESTED_TUNING = Tuning(
            name=(
                tuning_symbol
                + (f" capo {_capo_value}" if _capo_value else "")
            ),
            symbol=_sounded_symbol,
            notes=_sounded_notes,
            category="modern",
            popularity=0,
            key_strengths={},
            base_tuning=tuning_symbol,
            capo=_capo_value,
            fifth_string_note=fifth_string
        )

    elif capo is not None:

        raise ValueError("--capo requires --tuning to also be given.")

    if project_folder is not None:
        PROJECT_FOLDER = Path(project_folder)
    else:
        PROJECT_FOLDER = resolve_project_folder()


    class Tee:
        def __init__(self, *files):
            # BO-159 -- filter out None here, not just accept
            # whatever's passed. Confirmed directly: in a
            # PyInstaller windowed build (console=False, which
            # this application's own main.spec uses -- BO-158),
            # sys.stdout is genuinely None (no console attached
            # to write to at all), not merely absent/closed. The
            # call site below passes sys.stdout unconditionally,
            # so without this filter, Tee(None, log_file) would
            # silently capture that None, and the very first
            # print()/output() call afterward -- which is
            # everything this function does -- would crash with
            # AttributeError: 'NoneType' object has no attribute
            # 'write', reproduced directly this way before this
            # fix. write()/flush() below need no changes: they
            # already just iterate self.files, which now never
            # contains None.
            self.files = [f for f in files if f is not None]

        def write(self, text):
            for f in self.files:
                f.write(text)
                f.flush()

        def flush(self):
            for f in self.files:
                f.flush()


    # BO-160 -- resolution order: explicit per-call parameter >
    # saved setting > original hardcoded default. Confirmed
    # unaffected for every existing caller: the CLI never passes
    # scores_folder/output_folder explicitly (its own new
    # --scores-folder/--output-folder flags, see __main__ below,
    # populate these same parameters, so they follow this same
    # order too -- there's only one resolution path, not two),
    # and load_settings() itself returns {} whenever no settings
    # file has ever been saved, so .get(...) below is None and
    # every existing call falls through to the exact same
    # PROJECT_FOLDER / "scores" and PROJECT_FOLDER / "output"
    # this application always used.
    _settings = load_settings(PROJECT_FOLDER)

    if scores_folder is not None:
        SCORES_FOLDER = Path(scores_folder)
    elif _settings.get("scores_folder"):
        SCORES_FOLDER = Path(_settings["scores_folder"])
    else:
        SCORES_FOLDER = PROJECT_FOLDER / "scores"

    if output_folder is not None:
        OUTPUT_FOLDER = Path(output_folder)
    elif _settings.get("output_folder"):
        OUTPUT_FOLDER = Path(_settings["output_folder"])
    else:
        OUTPUT_FOLDER = PROJECT_FOLDER / "output"
    TAB_TEMPLATE_PATH = (
        PROJECT_FOLDER / "templates" / "TAB_linked_Treble_Example.mscz"
    )

    # BO-141 -- one timestamped run directory per BO execution,
    # generated once and reused for both the report and every
    # generated .mscz from this run -- no separate "generated"
    # subfolder at all (see create_run_folder()'s own docstring for
    # collision handling). RUN_FOLDER replaces the old, fixed
    # GENERATED_FOLDER at its own, single call site below.
    RUN_FOLDER = create_run_folder(OUTPUT_FOLDER)

    log_file = open(
        RUN_FOLDER / "BanjoOptimizer_report.txt",
        "w",
        encoding="utf-8"
    )

    original_stdout = sys.stdout

    sys.stdout = Tee(original_stdout, log_file)

    try:

        output(f"Banjo Optimizer v{VERSION}\n")

        # ---------------------------------------------------------
        # Development diagnostics (chord library, generator, melody
        # matching, etc.) have moved to dev_demos.py -- they no longer
        # run by default, so a normal use of this tool isn't buried
        # under ~9 diagnostic sections before the actual tuning report.
        # Run with --demos to see them, same output as before, just
        # opt-in now instead of automatic.
        # ---------------------------------------------------------

        if "--demos" in sys.argv:

            from dev_demos import run_all_demos

            run_all_demos()

        # ---------------------------------------------------------

        # BO-155 -- an explicit score_path bypasses the scores/-folder
        # lookup entirely (see this function's own docstring for why).
        # The existing score_filename branch below is untouched --
        # this only runs when score_path is actually given, which the
        # CLI itself never does.
        if score_path is not None:

            score_path = Path(score_path)

            if not score_path.exists() or score_path.suffix != ".mscz":

                raise ValueError(
                    f"{score_path} is not a valid .mscz file."
                )

            score_files = [score_path]

        else:

            score_files = sorted(
                SCORES_FOLDER.glob("*.mscz")
            )

            if score_filename is not None:

                score_files = [
                    f for f in score_files if f.name == score_filename
                ]

                if not score_files:

                    raise ValueError(
                        f"No file named {score_filename!r} found in "
                        f"{SCORES_FOLDER}."
                    )

        if not score_files:

            print(
                "No MuseScore files found."
            )


        else:

            print(
                f"Analyzing {len(score_files)} MuseScore file(s):"
            )



            for filename in score_files:


                score = MuseScoreFile(filename)



                score.open()



                score.read_title()

                # BO-143 -- read_composer() previously existed but was
                # never actually called anywhere in the real production
                # pipeline (confirmed directly, a pre-existing gap this
                # doesn't otherwise attempt to fix beyond making it
                # actually run) -- Score.composer stayed at its own
                # default ("") in every real run. Added here, alongside
                # the two new BO-143 reads it shares an identical
                # pattern with, since the task's own required composer
                # behavior depends on this actually running.
                score.read_composer()

                score.read_subtitle()

                score.read_lyricist()



                score.read_time_signature()



                staff_used = score.read_melody_notes()
                output(f"Using Staff {staff_used}")
                score.estimate_key()

                # Read harmonies from the same staff melody was read
                # from -- matches this project's established convention
                # (the banjo TAB staff carries both). Stored on
                # TuningAnalyzer for a future integration step (the
                # Playing Model); score_tuning() doesn't read it yet, so
                # this has no effect on the current score/recommendations.
                score.read_harmonies(staff_used)


                output(
                    "================================"
                )

                output(
                    "       Banjo Optimizer Report"
                )

                output(
                    "================================"
                )

                output(
                    ""
                )

                output(
                    "Score Information"
                )

                output(
                    "----------------"
                )

                output(
                    "Title:",
                    score.title
                )

                output(
                    "Key:",
                    score.key
                )

                output(
                    "Time Signature:",
                    score.time_signature
                )

                output(
                    "Total Notes:",
                    len(score.notes)
                )

                output(
                    ""
                )

                output(
                    "Optimization Results"
                )

                output(
                    "-------------------"
                )

                if REQUESTED_TUNING is not None:

                    output(
                        f"Using requested tuning: "
                        f"{REQUESTED_TUNING.symbol}"
                        + (
                            f" (open: {REQUESTED_TUNING.base_tuning}, "
                            f"capo {REQUESTED_TUNING.capo})"
                            if REQUESTED_TUNING.capo else ""
                        )
                        + "\n"
                    )

                    from models import TuningResult

                    rank = 1

                    top_results = [
                        TuningResult(
                            name=REQUESTED_TUNING.name,
                            symbol=REQUESTED_TUNING.symbol,
                            category=REQUESTED_TUNING.category
                        )
                    ]

                else:

                    analyzer = TuningAnalyzer(
                        score.notes,
                        score.key,
                        score.harmonies,
                        score.score.notes
                    )



                    results = analyzer.analyze()



                    output(
                        "\nRecommended Setups:\n"
                    )



                    rank = 1


                    top_results = apply_shared_features(
                        results["modern"][:num_tunings]
                    )

                    top_results = apply_confidence(top_results)


                if top_results and top_results[0].shared_features:

                    output(
                        "All of these:"
                    )

                    for feature in top_results[0].shared_features:

                        output(
                            "   -",
                            feature
                        )

                    print()


                for item in top_results:


                    output(
                        f"{rank}. {item.name} "
                        f"({item.symbol})"
                    )

                    for advantage in item.advantages:

                        output(
                            "   -",
                            advantage
                        )

                    if item.tradeoffs:

                        output(
                            "   Tradeoffs:"
                        )

                        for tradeoff in item.tradeoffs:

                            output(
                                "   -",
                                tradeoff
                            )

                    # A small gap to the nearest other option shown
                    # here is a genuine near-tie worth flagging -- an
                    # arbitrary but simple, self-relative threshold
                    # (5% of this result's own score), not a change to
                    # scoring/ranking itself.
                    if (
                        item.confidence is not None
                        and item.confidence < 0.05 * item.score
                    ):

                        output(
                            "   (Very close alternative to another "
                            "option above)"
                        )


                    print()


                    rank += 1


                # BO-140.4 -- additional alternatives, shown only when
                # explicitly requested (--alternatives > 0) and only
                # while candidates genuinely qualify as still-useful
                # (combined_score > 0, an existing, already-computed
                # field -- see select_additional_strong_alternatives()'s
                # own docstring for the full reasoning; this is
                # deliberately NOT the same 5% apply_confidence() test
                # used for the primary set's own "(Very close
                # alternative...)" text just above, which remains
                # completely unchanged). Default behavior
                # (--alternatives not given, or given as 0) is
                # completely unaffected: this block does not run at all
                # in that case.
                #
                # BO-151 -- initialized here (not just inside the if
                # below) so the .mscz-generation loop further down can
                # unconditionally build on it -- previously undefined
                # when --alternatives was 0/omitted, which is exactly
                # why generation never included these regardless of N:
                # generation used top_results alone, never this name at
                # all.
                additional = []

                if alternatives > 0:

                    additional = select_additional_strong_alternatives(
                        results["modern"][num_tunings:],
                        alternatives
                    )

                    if additional:

                        output(
                            "\nAdditional Strong Alternatives:\n"
                        )

                        for item in additional:

                            output(
                                f"{rank}. {item.name} "
                                f"({item.symbol})"
                            )

                            for advantage in item.advantages:

                                output(
                                    "   -",
                                    advantage
                                )

                            if item.tradeoffs:

                                output(
                                    "   Tradeoffs:"
                                )

                                for tradeoff in item.tradeoffs:

                                    output(
                                        "   -",
                                        tradeoff
                                    )

                            print()

                            rank += 1

                    else:

                        output(
                            "\nNo additional strong alternatives "
                            "found.\n"
                        )


                # ---------------------------------------------------------
                # Generate a playable .mscz for each recommended tuning
                # (see score_generator.py) -- uses the SAME top_results
                # already computed above, not a second recommendation
                # process.
                #
                # BO-27: TAB-only output. generate_chord_diagrams_only()
                # ("Plan B" -- see score_generator.py's own module notes
                # for its history) previously ran here too, producing a
                # second, separate file per tuning (chord diagrams on the
                # source's own notation staff, no TAB staff at all). That
                # function remains defined and intact in score_generator.py
                # (still covered by its own dedicated tests) -- this is a
                # narrower change to main.py's own generation loop, not a
                # removal of the function itself, matching this project's
                # own established pattern of keeping a superseded
                # generation path defined rather than deleted (see BO-19's
                # own treatment of generate_mscz()).
                # ---------------------------------------------------------

                output(
                    "Generating playable scores...\n"
                )

                generation_chord_service = ChordService(ChordLibrary())

                all_melody_exceptions = []

                # BO-153 -- structured, per-tuning generation results,
                # accumulated alongside (not instead of) the existing
                # output() calls below -- returned to the caller at
                # the end of this function, does not change any
                # existing text output.
                generated_files = []

                # BO-151 -- generate a playable .mscz for every requested
                # additional alternative too, not just the primary top 3.
                # Previously this loop iterated top_results alone, so
                # --alternatives N had no effect on generated files at
                # any N -- confirmed directly (BO-150 investigation)
                # that the text report already correctly reflected N,
                # only file generation did not. additional is always a
                # list here (empty when --alternatives is 0/omitted, via
                # its own initialization above), so default behavior
                # (no --alternatives given) is completely unchanged: the
                # loop still iterates exactly top_results in that case.
                generation_targets = top_results + additional

                for item in generation_targets:

                    try:

                        target_tuning = (
                            REQUESTED_TUNING
                            if REQUESTED_TUNING is not None
                            else get_tunings()[item.name]
                        )

                        (
                            tab_path, tab_shapes_applied, tab_shapes_skipped,
                            melody_exceptions
                        ) = generate_tab_from_template(
                            score,
                            target_tuning,
                            staff_used,
                            TAB_TEMPLATE_PATH,
                            RUN_FOLDER,
                            generation_chord_service
                        )

                        output(
                            f"   Generated: {tab_path.name} "
                            f"({tab_shapes_applied} chord shapes"
                            + (
                                f", {tab_shapes_skipped} chord symbols "
                                "skipped"
                                if tab_shapes_skipped else ""
                            )
                            + (
                                f", {len(melody_exceptions)} melody/chord "
                                "exceptions"
                                if melody_exceptions else ""
                            )
                            + ")"
                        )

                        all_melody_exceptions.extend(melody_exceptions)

                        generated_files.append({
                            "tuning_name": item.name,
                            "tab_path": tab_path,
                            "tab_shapes_applied": tab_shapes_applied,
                            "tab_shapes_skipped": tab_shapes_skipped,
                            "melody_exceptions": melody_exceptions,
                            "error": None,
                        })

                    except Exception as error:

                        output(
                            f"   Could not generate a score for "
                            f"{item.name}: {error}"
                        )

                        generated_files.append({
                            "tuning_name": item.name,
                            "tab_path": None,
                            "tab_shapes_applied": None,
                            "tab_shapes_skipped": None,
                            "melody_exceptions": [],
                            "error": str(error),
                        })

                print()

                # -----------------------------------------------------
                # Melody/Chord Exceptions -- BO-21. A chord had a melody
                # note at its own onset, but no practical chord shape
                # containing that exact pitch existed, so the normal
                # best fallback shape was used and marked red in the
                # generated FretDiagram (see score_generator.py's own
                # _apply_chord_shapes()/_set_fret_diagram_content() for
                # the detection/marking itself -- this is purely
                # reporting what those already found). Only printed when
                # at least one exists, matching this project's own
                # existing convention of not printing empty sections.
                # -----------------------------------------------------

                if all_melody_exceptions:

                    output(
                        "Melody/Chord Exceptions\n"
                        "-----------------------\n"
                    )

                    for index, exception in enumerate(
                        all_melody_exceptions, start=1
                    ):

                        output(
                            f"{index}. Measure {exception['measure']}, "
                            f"beat {exception['beat']}"
                        )

                        if "reason" in exception:

                            # An unreachable-pitch exception (this
                            # note's own melody pitch has no possible
                            # fret/string in this tuning at all -- a
                            # genuinely different situation from BO-21's
                            # own "no practical shape contains this
                            # pitch" chord exceptions below, so it's
                            # reported with its own, differently-shaped
                            # fields rather than forcing it into the
                            # chord-specific format).

                            output(
                                f"   Melody pitch: {exception['melody_pitch']}"
                            )

                            output(
                                f"   Tuning: {exception['tuning_symbol']}"
                            )

                            output(f"   {exception['reason']}.\n")

                            continue

                        output(f"   Chord: {exception['chord_symbol']}")

                        output(f"   Melody: {exception['melody_pitch']}")

                        output(
                            f"   Selected shape: "
                            f"{exception['selected_shape']}"
                        )

                        output(f"   Tuning: {exception['tuning_symbol']}")

                        output(
                            "   No practical chord shape containing "
                            "the melody pitch was found.\n"
                        )

                # BO-153 -- structured per-score result, accumulated
                # for the caller. Built from data already computed
                # above in this same loop iteration -- does not
                # change any existing text output.
                all_scores_results.append({
                    "filename": filename.name,
                    "title": score.title,
                    "key": score.key,
                    "time_signature": score.time_signature,
                    "total_notes": len(score.notes),
                    "staff_used": staff_used,
                    "requested_tuning": REQUESTED_TUNING,
                    "recommendations": top_results,
                    "additional_alternatives": additional,
                    "generated_files": generated_files,
                })



                # print(
                    # "\nHistorical Alternatives:\n"
                # )



                # rank = 1


                # for item in results["historical"][:1]:

                    # output(
                       # f"{rank}. {item['name']} "
                       # f"({item['symbol']})"
                    # )

                    # for reason in item["reasons"]:

                        # output(
                           # "   -",
                           # reason
                        # )


                    # print()


                    # rank += 1

        return {
            "run_folder": RUN_FOLDER,
            "report_path": RUN_FOLDER / "BanjoOptimizer_report.txt",
            "scores": all_scores_results,
        }

    finally:

        # BO-170 -- always restore the global sys.stdout and
        # close this run's own report file, even if the body
        # above raised. Confirmed real defect this fixes: without
        # this, every GUI "Optimize" click (gui.py calls this
        # function directly, synchronously, in-process -- not a
        # subprocess) leaves this run's own report file open and
        # nests a new Tee around the previous, still-unrestored
        # sys.stdout -- an accumulating chain that keeps every
        # prior run's own output folder locked on Windows until
        # the whole GUI process exits (BO-170's own investigation).
        sys.stdout = original_stdout

        log_file.close()


if __name__ == "__main__":

    arg_parser = argparse.ArgumentParser(add_help=False)

    arg_parser.add_argument("--score", default=None)

    arg_parser.add_argument("--tuning", default=None)

    arg_parser.add_argument("--capo", type=int, default=None)

    # BO-140.4 -- replaces BO-140.1's own --recommendations (which
    # meant "N total recommendations", confirmed confusing since
    # rank 4+ is a genuinely different, secondary tier, not simply
    # "more of the same top-N list"). Removed cleanly rather than
    # aliased under the old name: the same flag name with a
    # genuinely different meaning (total vs. additional) would
    # itself actively mislead a user who learned the old semantics,
    # which is worse than a clean break.
    arg_parser.add_argument(
        "--alternatives", type=int, default=0
    )

    # BO-160 -- one-off, per-run overrides only, same convention
    # as --score itself: neither of these saves anything. Saving
    # a new default scores/output location happens only via the
    # GUI's own Settings dialog, which calls save_settings()
    # directly.
    arg_parser.add_argument("--scores-folder", default=None)

    arg_parser.add_argument("--output-folder", default=None)

    cli_args, _unused_remaining_args = (
        arg_parser.parse_known_args()
    )

    if cli_args.alternatives < 0:

        print("--alternatives must be 0 or greater.")

        sys.exit(1)

    try:

        run_optimizer(
            score_filename=cli_args.score,
            tuning_symbol=cli_args.tuning,
            capo=cli_args.capo,
            alternatives=cli_args.alternatives,
            scores_folder=cli_args.scores_folder,
            output_folder=cli_args.output_folder,
        )

    except ValueError as error:

        print(str(error))

        sys.exit(1)
