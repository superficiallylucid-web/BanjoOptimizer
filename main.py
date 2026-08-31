from pathlib import Path
import sys
import os
import argparse

from output import output, clear_output

from parser import MuseScoreFile
from optimizer import TuningAnalyzer
from recommendations import apply_shared_features, apply_confidence
from score_generator import generate_tab_from_template
from tunings import get_tunings
from chord_service import ChordService
from chord_library import ChordLibrary
from models import Tuning

VERSION = "1.0"

clear_output()

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


arg_parser = argparse.ArgumentParser(add_help=False)

arg_parser.add_argument("--score", default=None)

arg_parser.add_argument("--tuning", default=None)

arg_parser.add_argument("--capo", type=int, default=None)

cli_args, _unused_remaining_args = arg_parser.parse_known_args()

REQUESTED_TUNING = None

if cli_args.tuning is not None:

    _open_notes = _parse_tuning_symbol(cli_args.tuning)

    if _open_notes is None:

        print(
            f"Could not parse --tuning {cli_args.tuning!r} -- "
            f"expected a 5-character-ish symbol like 'gDGBD' "
            f"(5th string, then strings 1-4, each optionally "
            f"followed by '#' or 'b')."
        )

        sys.exit(1)

    if cli_args.capo is not None and not (1 <= cli_args.capo <= 5):

        print("--capo must be between 1 and 5.")

        sys.exit(1)

    _capo_value = cli_args.capo if cli_args.capo is not None else 0

    # Capo shifts strings 1-4 ONLY (indices 1-4 of notes) --
    # never the 5th string (index 0), confirmed directly as a
    # real-world, physical fact earlier in this project.
    _sounded_notes = [_open_notes[0]] + [
        note + _capo_value for note in _open_notes[1:]
    ]

    _sounded_symbol = _notes_to_symbol(_sounded_notes)

    # name includes the capo value (when given) so the generated
    # filename (built elsewhere from tuning.name and tuning.
    # symbol) is genuinely unique per capo value -- confirmed
    # real, not merely cosmetic: without this, different --capo
    # values for the same --tuning silently overwrote each
    # other's output file.
    REQUESTED_TUNING = Tuning(
        name=(
            cli_args.tuning
            + (f" capo {_capo_value}" if _capo_value else "")
        ),
        symbol=_sounded_symbol,
        notes=_sounded_notes,
        category="modern",
        popularity=0,
        key_strengths={},
        base_tuning=cli_args.tuning,
        capo=_capo_value,
        fifth_string_note=None
    )

elif cli_args.capo is not None:

    print("--capo requires --tuning to also be given.")

    sys.exit(1)

if getattr(sys, "frozen", False):
    PROJECT_FOLDER = Path(sys.executable).parent
else:
    PROJECT_FOLDER = Path(__file__).parent


class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, text):
        for f in self.files:
            f.write(text)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()


SCORES_FOLDER = PROJECT_FOLDER / "scores"
OUTPUT_FOLDER = PROJECT_FOLDER / "output"
GENERATED_FOLDER = OUTPUT_FOLDER / "generated"
TAB_TEMPLATE_PATH = (
    PROJECT_FOLDER / "templates" / "TAB_linked_Treble_Example.mscz"
)

OUTPUT_FOLDER.mkdir(exist_ok=True)
GENERATED_FOLDER.mkdir(exist_ok=True)

log_file = open(
    OUTPUT_FOLDER / "BanjoOptimizer_report.txt",
    "w",
    encoding="utf-8"
)

sys.stdout = Tee(sys.stdout, log_file)

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

score_files = sorted(
    SCORES_FOLDER.glob("*.mscz")
)

if cli_args.score is not None:

    score_files = [
        f for f in score_files if f.name == cli_args.score
    ]

    if not score_files:

        print(
            f"No file named {cli_args.score!r} found in "
            f"{SCORES_FOLDER}."
        )

        sys.exit(1)

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
                results["modern"][:3]
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

        for item in top_results:

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
                    GENERATED_FOLDER,
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

            except Exception as error:

                output(
                    f"   Could not generate a score for "
                    f"{item.name}: {error}"
                )

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
 