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
from music import (
    note_name_to_pitch_class,
    midi_to_note_name,
    pitch_name
)
from fretboard import (
    sounding_notes,
    find_melody_occurrences,
    calculate_shape_metadata
)

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
# Shows the generator's candidates for a few Major chords in
# Open G, labeled full vs. reduced/rescue so it's obvious at a
# glance which voicings are the default (full) and which only
# exist because a full voicing was impractical (reduced/
# rescue). Not connected to scoring or the report. Safe to
# delete this block once it's no longer needed.

output("--- Chord Generator Demo (temporary) ---")

open_g = get_tunings()["Open G"]

for demo_root, demo_root_pc, demo_quality in [
    ("C", 0, "Major"),
    ("G", 7, "Major"),
    ("E", 4, "Major"),
]:

    generated_matches = generate_candidates(
        tuning=open_g,
        root=demo_root,
        root_pc=demo_root_pc,
        quality_code="",
        quality_display=demo_quality
    )

    output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

    for match in generated_matches:

        voicing_type = (
            "reduced/rescue" if "--" in match.shape else "full"
        )

        output(
            f"    {match.shape:<8}",
            f" {voicing_type:<15}",
            f" {match.inversion}, top {match.top_note}"
        )

output("\n--- End Chord Generator Demo ---\n")

# ---------------------------------------------------------
# TEMPORARY: inversion / top note demo
# ---------------------------------------------------------
#
# Shows, for each generated candidate, its shape, identified
# inversion, and the highest-sounding note in that voicing.
# Not used in scoring or ranking -- this is groundwork for
# future melody-note matching. Not connected to the report.
# Safe to delete this block once it's no longer needed.

output("--- Inversion / Top Note Demo (temporary) ---")

for demo_root, demo_root_pc, demo_quality in [
    ("C", 0, "Major"),
    ("G", 7, "Major"),
    ("E", 4, "Major"),
]:

    generated_matches = generate_candidates(
        tuning=open_g,
        root=demo_root,
        root_pc=demo_root_pc,
        quality_code="",
        quality_display=demo_quality
    )

    output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

    for match in generated_matches:

        output(
            f"    {match.shape}",
            f" {match.inversion}",
            f" (top note: {match.top_note})"
        )

output("\n--- End Inversion / Top Note Demo ---\n")

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
# TEMPORARY: melody / chord shape demo
# ---------------------------------------------------------
#
# Shows get_shapes_for_melody() reordering the same merged
# list from the Chord Service Demo above to prefer shapes
# whose top note matches a given melody note. Calls the real
# ChordService -- nothing here is hard-coded. Not connected to
# scoring, the report, or tuning recommendations. Safe to
# delete this block once it's no longer needed.

output("--- Melody / Chord Shape Demo (temporary) ---")

for melody_note in ["E", "D"]:

    shapes = chord_service.get_shapes_for_melody(
        tuning=open_g,
        root="C",
        root_pc=0,
        quality_code="",
        quality_display="Major",
        melody_note=melody_note
    )

    output(f"\nC Major, melody note {melody_note}:")

    for rank, shape in enumerate(shapes, start=1):

        match_label = ""

        if (
            note_name_to_pitch_class(shape.top_note)
            == note_name_to_pitch_class(melody_note)
        ):

            match_label = "  MELODY MATCH"

        output(
            f"    {rank}. {shape.shape}",
            f"[{shape.source}]",
            f" top={shape.top_note}{match_label}"
        )

# Real-data check: pull a real chord occurrence and its melody
# note from an actual tracked score (White Christmas has real
# Harmony/chord-symbol data), then feed that real root/quality/
# melody note straight into the real ChordService ranking --
# nothing in this block is hard-coded, all of it comes from
# parsing the actual file.
output("\nReal-data check (White Christmas):")

white_christmas = MuseScoreFile(
    SCORES_FOLDER / "White Christmas (G (gCGBD)).mscz"
)

white_christmas.open()
white_christmas.read_melody_notes()
white_christmas.read_harmonies(4)

major_harmony = None

for harmony in white_christmas.score.harmonies:

    if harmony.quality_code == "":

        major_harmony = harmony

        break

if major_harmony is not None:

    root_name = pitch_name(major_harmony.root_pc)

    melody_midi = white_christmas.score.melody_note_for_harmony(
        major_harmony
    )

    melody_note_name = (
        midi_to_note_name(melody_midi)
        if melody_midi is not None
        else None
    )

    output(
        f"    Measure {major_harmony.measure}: "
        f"{major_harmony.symbol} -- melody note "
        f"{melody_note_name or '(none found)'}"
    )

    if melody_note_name is not None:

        real_shapes = chord_service.get_shapes_for_melody(
            tuning=open_g,
            root=root_name,
            root_pc=major_harmony.root_pc,
            quality_code="",
            quality_display="Major",
            melody_note=melody_note_name
        )

        for rank, shape in enumerate(real_shapes, start=1):

            output(
                f"      {rank}. {shape.shape}",
                f"[{shape.source}]",
                f" top={shape.top_note}"
            )

else:

    output(
        "    No Major-quality chord found in this score's "
        "Harmony data."
    )

output("\n--- End Melody / Chord Shape Demo ---\n")

# ---------------------------------------------------------
# TEMPORARY: melody occurrence demo
# ---------------------------------------------------------
#
# Shows that "melody match" and "top note match" are NOT the
# same question. find_melody_occurrences() checks every
# sounding string, not just the highest -- this uses a shape
# where the melody note occurs on an inner voice, so it's
# obvious the two concepts differ. Not connected to ranking,
# scoring, or the report -- this only demonstrates the new
# detection capability itself (see get_shapes_for_melody's
# docstring for why ranking hasn't changed yet). Safe to
# delete this block once it's no longer needed.

output("--- Melody Occurrence Demo (temporary) ---")

demo_shape = "0000"

demo_melody_note = "B"

all_notes = sounding_notes(open_g, demo_shape)

_, demo_top_note = calculate_shape_metadata(
    open_g, demo_shape, 7, ""
)

occurrences = find_melody_occurrences(
    open_g, demo_shape, demo_melody_note
)

output(f"\nG Major shape: {demo_shape}")

output(
    "  All sounding notes:",
    ", ".join(n.name for n in all_notes)
)

output(f"  top_note: {demo_top_note}")

output(f"  Requested melody note: {demo_melody_note}")

if occurrences:

    matches = ", ".join(
        f"string {o.string_index} ({o.name})"
        for o in occurrences
    )

    output(f"  Melody match found on: {matches}")

    output(
        "  -> melody match != top note match:",
        f"{demo_melody_note} is NOT the top note ({demo_top_note}),",
        "but it IS genuinely present in this chord"
    )

else:

    output("  No melody match found.")

output("\n--- End Melody Occurrence Demo ---\n")

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
 