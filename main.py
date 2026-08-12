from pathlib import Path
import sys
import os

from output import output, clear_output

from parser import MuseScoreFile
from optimizer import TuningAnalyzer
from recommendations import apply_shared_features, apply_confidence

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
 