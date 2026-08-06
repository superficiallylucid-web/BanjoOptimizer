from pathlib import Path
import sys
import os

from output import output, clear_output

from parser import MuseScoreFile
from optimizer import TuningAnalyzer
from recommendations import apply_shared_features
from chord_library import ChordLibrary
from chord_generator import generate_candidates
from chord_service import ChordService
from playability import evaluate as evaluate_playability
from tunings import get_tunings

VERSION = "1.0"

clear_output()

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

OUTPUT_FOLDER.mkdir(exist_ok=True)

log_file = open(
    OUTPUT_FOLDER / "BanjoOptimizer_report.txt",
    "w",
    encoding="utf-8"
)

sys.stdout = Tee(sys.stdout, log_file)

output(f"Banjo Optimizer v{VERSION}\n")

# ---------------------------------------------------------
# TEMPORARY: chord library architecture demo
# ---------------------------------------------------------
#
# Validates ChordLibrary / ChordShape only -- not connected
# to scoring or recommendations yet. Safe to delete this
# block once real integration exists.

output("--- Chord Library Demo (temporary) ---")

chord_library = ChordLibrary()

chord_library.load(
    "banjo_chord_library - gDGBD Chord Shapes.csv"
)

for demo_root, demo_quality in [
    ("C", "Major"),
    ("G", "Major"),
    ("E", "Major"),
]:

    matches = chord_library.find(
        "gDGBD",
        demo_root,
        demo_quality
    )

    output(f"{demo_root} {demo_quality}:")

    for match in matches:

        output(
            f"   shape={match.shape}",
            f"comfort={match.comfort_code}",
            f"({match.comfort_explanation})"
        )

output("--- End Chord Library Demo ---\n")

# ---------------------------------------------------------
# TEMPORARY: chord library statistics demo
# ---------------------------------------------------------
#
# Development/validation only -- lets you check how complete
# the library is as more tunings and shapes get filled in.
# Not connected to scoring or the report. Safe to delete this
# block once it's no longer needed for validation.

output("--- Chord Library Statistics (temporary) ---")

stats = chord_library.statistics()

output(f"Tuning files loaded: {stats['tunings_loaded']}")

for tuning_symbol, tuning_stats in stats["by_tuning"].items():

    output(f"\n{tuning_symbol}:")

    output(f"  Total shapes: {tuning_stats['total']}")

    output(f"  Verified: {tuning_stats['verified']}")

    output(
        "  Candidate (unverified):",
        tuning_stats['candidate']
    )

    output(
        "  Unspecified verification:",
        tuning_stats['unspecified']
    )

    output("  By quality:")

    for quality, count in tuning_stats["by_quality"].items():

        output(f"    {quality}: {count}")

totals = stats["totals"]

output("\nGrand totals:")

output(f"  Total shapes: {totals['total']}")

output(f"  Verified: {totals['verified']}")

output("  Candidate (unverified):", totals['candidate'])

output(
    "  Unspecified verification:",
    totals['unspecified']
)

output("  By quality:")

for quality, count in totals["by_quality"].items():

    output(f"    {quality}: {count}")

output("--- End Chord Library Statistics ---\n")

# ---------------------------------------------------------
# TEMPORARY: chord generator demo
# ---------------------------------------------------------
#
# First, small proof of the fretboard-search chord generator:
# one tuning (Open G), a few Major chords, printed alongside
# the existing verified library data so they can be compared
# by eye. Not merged/combined -- that's chord_service.py,
# future work. Not connected to scoring or the report. Safe
# to delete this block once it's no longer needed.

output("--- Chord Generator Demo (temporary) ---")

open_g = get_tunings()["Open G"]

for demo_root, demo_root_pc, demo_quality in [
    ("C", 0, "Major"),
    ("G", 7, "Major"),
    ("E", 4, "Major"),
]:

    verified_matches = chord_library.find(
        "gDGBD",
        demo_root,
        demo_quality
    )

    generated_matches = generate_candidates(
        tuning=open_g,
        root=demo_root,
        root_pc=demo_root_pc,
        quality_code="",
        quality_display=demo_quality
    )

    output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

    output("  Verified:")

    for match in verified_matches:

        output(f"    {match.shape}")

    output("  Generated candidates:")

    for rank, match in enumerate(generated_matches, start=1):

        output(f"    {rank}. {match.shape}")

output("\n--- End Chord Generator Demo ---\n")

# ---------------------------------------------------------
# TEMPORARY: playability filter demo
# ---------------------------------------------------------
#
# Shows every RAW generated candidate (before chord_service's
# filtering) run through playability.evaluate() individually,
# so both accepted and rejected shapes are visible side by
# side with their score and reason. This is the unfiltered
# view -- the chord service demo below shows what's left
# after rejected candidates are already removed. Not
# connected to scoring or the report. Safe to delete this
# block once it's no longer needed.

output("--- Playability Filter Demo (temporary) ---")

for demo_root, demo_root_pc, demo_quality in [
    ("C", 0, "Major"),
    ("G", 7, "Major"),
    ("E", 4, "Major"),
]:

    raw_candidates = generate_candidates(
        tuning=open_g,
        root=demo_root,
        root_pc=demo_root_pc,
        quality_code="",
        quality_display=demo_quality
    )

    output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

    for candidate in raw_candidates:

        result = evaluate_playability(candidate.shape)

        status = "ACCEPTED" if result.accepted else "REJECTED"

        output(
            f"    {candidate.shape}  {status}",
            f" score={result.score}",
            f" - {result.reason}"
        )

        for warning in result.warnings:

            output(f"        warning: {warning}")

output("\n--- End Playability Filter Demo ---\n")

# ---------------------------------------------------------
# TEMPORARY: chord service demo
# ---------------------------------------------------------
#
# Shows ChordService's merged, deduplicated output for a few
# sample chords -- verified shapes first (library order),
# then generated candidates that aren't already covered by a
# verified shape. No ranking logic beyond that ordering yet
# (see chord_service.py's docstring for what's deliberately
# left out). Not connected to scoring or the report. Safe to
# delete this block once it's no longer needed.

output("--- Chord Service Demo (temporary) ---")

chord_service = ChordService(chord_library)

for demo_root, demo_root_pc, demo_quality in [
    ("C", 0, "Major"),
    ("G", 7, "Major"),
    ("E", 4, "Major"),
]:

    merged = chord_service.get_shapes(
        tuning=open_g,
        root=demo_root,
        root_pc=demo_root_pc,
        quality_code="",
        quality_display=demo_quality
    )

    output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

    for rank, shape in enumerate(merged, start=1):

        output(
            f"    {rank}. {shape.shape}",
            f"[{shape.source}]"
        )

output("\n--- End Chord Service Demo ---\n")

# ---------------------------------------------------------

score_files = sorted(
    SCORES_FOLDER.glob("*.mscz")
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



        score.read_time_signature()



        staff_used = score.read_melody_notes()
        output(f"Using Staff {staff_used}")
        score.estimate_key()


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
       
        analyzer = TuningAnalyzer(
            score.notes,
            score.key
        )



        results = analyzer.analyze()



        output(
            "\nRecommended Setups:\n"
        )



        rank = 1


        top_results = apply_shared_features(
            results["modern"][:3]
        )


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


            print()


            rank += 1



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
 