from pathlib import Path
import sys
import os

from output import output, clear_output

from parser import MuseScoreFile
from optimizer import TuningAnalyzer

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



        # Currently using Staff 4 as the melody staff
        score.read_staff_notes(4)
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


        for item in results["modern"][:3]:


            output(
                f"{rank}. {item['name']} "
                f"({item['symbol']})"
            )
            
            for reason in item["reasons"]:

                output(
                    "   -",
                    reason
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
 