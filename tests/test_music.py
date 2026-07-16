"""
Basic tests for Banjo Optimizer.

Tests:
- MuseScore loading
- title extraction
- note extraction
- key estimation
- tuning recommendations
"""


from pathlib import Path

from parser import MuseScoreFile
from optimizer import TuningAnalyzer



TEST_FOLDER = Path(__file__).parent



# ---------------------------------------------------------
# Find score by title fragment
# ---------------------------------------------------------

def find_score_file(title_fragment):

    for file in TEST_FOLDER.glob("*.mscz"):

        if title_fragment.lower() in file.name.lower():

            return file


    raise FileNotFoundError(
        f"No score found containing: {title_fragment}"
    )



# ---------------------------------------------------------
# Load score helper
# ---------------------------------------------------------

def load_score(title_fragment):

    path = find_score_file(
        title_fragment
    )


    score = MuseScoreFile(
        path
    )


    score.open()

    score.read_title()

    score.read_time_signature()

    score.read_staff_notes(
        4
    )

    score.estimate_key()


    return score



# ---------------------------------------------------------
# White Christmas
# ---------------------------------------------------------

def test_white_christmas():

    score = load_score(
        "White Christmas"
    )


    assert score.title == "White Christmas"

    assert len(score.notes) > 0

    assert score.key == "G major"



    analyzer = TuningAnalyzer(
        score.notes,
        score.key
    )


    results = analyzer.analyze()


    assert len(
        results["modern"]
    ) > 0



# ---------------------------------------------------------
# My Favorite Things
# ---------------------------------------------------------

def test_my_favorite_things():

    score = load_score(
        "My Favorite Things"
    )


    assert score.title == "My Favorite Things"

    assert len(score.notes) > 0

    assert score.key == "E minor"



    analyzer = TuningAnalyzer(
        score.notes,
        score.key
    )


    results = analyzer.analyze()


    assert len(
        results["modern"]
    ) > 0



# ---------------------------------------------------------
# Basic score integrity
# ---------------------------------------------------------

def test_note_extraction():

    files = list(
        TEST_FOLDER.glob(
            "*.mscz"
        )
    )


    # Confirm test folder contains scores

    assert len(files) >= 3



    for file in files:


        score = MuseScoreFile(
            file
        )


        score.open()


        score.read_staff_notes(
            4
        )


        assert len(
            score.notes
        ) > 0
        
        # ---------------------------------------------------------
# Cousin Sally Brown
# ---------------------------------------------------------

def test_cousin_sally_brown():

    score = load_score(
        "Cousin Sally Brown"
    )


    assert score.title == "Cousin Sally Brown"

    assert len(score.notes) > 0

    assert score.key == "D major"



    analyzer = TuningAnalyzer(
        score.notes,
        score.key
    )


    results = analyzer.analyze()


    assert len(
        results["modern"]
    ) > 0
    # ---------------------------------------------------------
# Tuning recommendation sanity checks
# ---------------------------------------------------------

def test_white_christmas_recommends_open_g():

    score = load_score(
        "White Christmas"
    )


    analyzer = TuningAnalyzer(
        score.notes,
        score.key
    )


    results = analyzer.analyze()


    best = results["modern"][0]


    assert best["name"] == "Open G"



def test_cousin_sally_brown_recommends_double_d():

    score = load_score(
        "Cousin Sally Brown"
    )


    analyzer = TuningAnalyzer(
        score.notes,
        score.key
    )


    results = analyzer.analyze()


    best = results["modern"][0]


    assert best["name"] == "Double D"



def test_my_favorite_things_has_reasonable_recommendation():

    score = load_score(
        "My Favorite Things"
    )


    analyzer = TuningAnalyzer(
        score.notes,
        score.key
    )


    results = analyzer.analyze()


    best = results["modern"][0]


    assert best["name"] in [
        "C Standard",
        "Open G",
        "Old G",
        "G Minor",
        "Double C"
    ]