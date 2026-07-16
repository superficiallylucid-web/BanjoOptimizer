from pathlib import Path

from parser import MuseScoreFile
from optimizer import TuningAnalyzer


PROJECT_FOLDER = Path(__file__).parent

SCORES_FOLDER = PROJECT_FOLDER / "scores"



print("Banjo Optimizer\n")



score_files = sorted(
    SCORES_FOLDER.glob("*.mscz")
)



if not score_files:

    print(
        "No MuseScore files found."
    )


else:

    print(
        f"Found {len(score_files)} MuseScore file(s):"
    )



    for filename in score_files:


        score = MuseScoreFile(filename)



        score.open()



        score.read_title()



        score.read_time_signature()



        # Currently using Staff 4 as the melody staff
        score.read_staff_notes(4)



        score.estimate_key()



        analyzer = TuningAnalyzer(
            score.notes,
            score.key
        )



        results = analyzer.analyze()



        print(
            "\nModern Tuning Recommendations:\n"
        )



        rank = 1


        for item in results["modern"]:


            print(
                f"{rank}. {item['name']} "
                f"({item['symbol']}): "
                f"{item['score']}"
            )


            for reason in item["reasons"]:

                print(
                    "   -",
                    reason
                )


            print()


            rank += 1



        print(
            "\nHistorical Alternatives:\n"
        )



        rank = 1


        for item in results["historical"]:


            print(
                f"{rank}. {item['name']} "
                f"({item['symbol']}): "
                f"{item['score']}"
            )


            for reason in item["reasons"]:

                print(
                    "   -",
                    reason
                )


            print()


            rank += 1



        print(
            "-------------------------"
        )

        print(
            "Title:",
            score.title
        )

        print(
            "Key:",
            score.key
        )

        print(
            "Time Signature:",
            score.time_signature
        )

        print(
            "Total Notes:",
            len(score.notes)
        )

        print(
            "-------------------------"
        )