from pathlib import Path
import sys
import os

from output import output, clear_output

from parser import MuseScoreFile
from optimizer import TuningAnalyzer
from recommendations import apply_shared_features, apply_confidence
from score_generator import (
    generate_chord_diagrams_only, generate_tab_from_template
)
from tunings import get_tunings
from chord_service import ChordService
from chord_library import ChordLibrary

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
GENERATED_FOLDER = OUTPUT_FOLDER / "generated"
TAB_TEMPLATE_PATH = (
    PROJECT_FOLDER / "templates" / "TAB_linked_Treble_Example.mscz"
)

OUTPUT_FOLDER.mkdir(exist_ok=True)

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
        # Currently using generate_chord_diagrams_only() ("Plan
        # B"): adds banjo chord shape diagrams above the existing
        # chord symbols on the score's own notation staff, without
        # creating a TAB staff and without touching melody notes/
        # frets/strings/pitches or any existing TAB elsewhere in
        # the score. Adopted after repeated, unresolved MuseScore
        # "Incomplete measure" errors on the full TAB-generation
        # path (generate_mscz(), still defined in score_generator.py
        # and intended to be revisited later) -- each confirmed
        # structural gap found and fixed did not resolve the
        # underlying issue, so this narrower, lower-risk approach
        # was adopted instead.
        # ---------------------------------------------------------

        output(
            "Generating playable scores...\n"
        )

        generation_chord_service = ChordService(ChordLibrary())

        all_melody_exceptions = []

        for item in top_results:

            try:

                target_tuning = get_tunings()[item.name]

                (
                    generated_path, shapes_applied, shapes_skipped,
                    melody_exceptions
                ) = generate_chord_diagrams_only(
                    score,
                    target_tuning,
                    staff_used,
                    GENERATED_FOLDER,
                    generation_chord_service
                )

                output(
                    f"   Generated: {generated_path.name} "
                    f"({shapes_applied} chord shapes"
                    + (
                        f", {shapes_skipped} chord symbols "
                        "skipped"
                        if shapes_skipped else ""
                    )
                    + (
                        f", {len(melody_exceptions)} melody/chord "
                        "exceptions"
                        if melody_exceptions else ""
                    )
                    + ")"
                )

                all_melody_exceptions.extend(melody_exceptions)

                # BO-23: also generate a TAB-only score from the
                # MuseScore-created template (see score_generator.py's
                # own BO-23 section notes) -- a separate, additive
                # output alongside the existing chord-diagrams-only
                # one above, not a replacement for it. Uses the SAME
                # underlying chord-shape selection (_apply_chord_
                # shapes(), unmodified) with the same harmonies/
                # melody/tuning, so its own melody/chord exceptions
                # are identical to the ones already collected above --
                # deliberately not added a second time here, to avoid
                # reporting the same exception twice.
                (
                    tab_path, tab_shapes_applied, tab_shapes_skipped,
                    _
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
                    + ")"
                )

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
 