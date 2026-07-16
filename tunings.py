from models import Tuning


def get_tunings():
    """
    Returns all supported banjo tunings.

    Notes are MIDI numbers for the open strings
    ordered from the short 5th string to the 1st string.
    """

    return {

        # =====================================================
        # Modern 5-string tunings
        # =====================================================

        "Open G": Tuning(
            name="Open G",
            symbol="gDGBD",
            notes=[67, 50, 55, 59, 62],
            category="modern",
            popularity=10,
            key_strengths={
                "G major": 15,
                "E minor": 8,
                "D major": 6
            }
        ),

        "C Standard": Tuning(
            name="C Standard",
            symbol="gCGBD",
            notes=[67, 48, 55, 59, 62],
            category="modern",
            popularity=10,
            key_strengths={
                "C major": 15,
                "G major": 8,
                "E minor": 6
            }
        ),

        "Double C": Tuning(
            name="Double C",
            symbol="gCGCD",
            notes=[67, 48, 55, 60, 62],
            category="modern",
            popularity=9,
            key_strengths={
                "C major": 14,
                "D major": 8
            }
        ),

        "Double D": Tuning(
            name="Double D",
            symbol="aDADE",
            notes=[69, 50, 57, 62, 64],
            category="modern",
            popularity=9,
            key_strengths={
                "D major": 15,
                "E minor": 5
            },
            base_tuning="Double C (gCGCD)",
            capo=2,
            fifth_string_note="A"
        ),

        "A Modal Sawmill": Tuning(
            name="A Modal Sawmill",
            symbol="aEADE",
            notes=[69, 52, 57, 62, 64],
            category="modern",
            popularity=8,
            key_strengths={
                "E minor": 14,
                "A minor": 12
            }
        ),

        "G Modal Sawmill": Tuning(
            name="G Modal Sawmill",
            symbol="gDGCD",
            notes=[67, 50, 55, 60, 62],
            category="modern",
            popularity=7,
            key_strengths={
                "G minor": 13,
                "G major": 6
            }
        ),

        "G Minor": Tuning(
            name="G Minor",
            symbol="gDGBbD",
            notes=[67, 50, 55, 58, 62],
            category="modern",
            popularity=5,
            key_strengths={
                "G minor": 15,
                "E minor": 12
            }
        ),

        "Old G": Tuning(
            name="Old G",
            symbol="gDGDE",
            notes=[67, 50, 55, 62, 64],
            category="modern",
            popularity=5,
            key_strengths={
                "E minor": 10,
                "G major": 8
            }
        ),

        "Open C": Tuning(
            name="Open C",
            symbol="gCGCE",
            notes=[67, 48, 55, 60, 64],
            category="modern",
            popularity=4,
            key_strengths={
                "C major": 12
            }
        ),

        "Open A": Tuning(
            name="Open A",
            symbol="aEAC#E",
            notes=[69, 52, 57, 61, 64],
            category="modern",
            popularity=3,
            key_strengths={
                "A major": 15
            }
        ),

        "A Minor": Tuning(
            name="A Minor",
            symbol="aEACE",
            notes=[69, 52, 57, 60, 64],
            category="modern",
            popularity=3,
            key_strengths={
                "A minor": 15
            }
        ),

        # =====================================================
        # Historical tunings
        # =====================================================

        "Triple D Darling Cora": Tuning(
            name="Triple D Darling Cora",
            symbol="f#DADD",
            notes=[66, 50, 57, 62, 62],
            category="historical",
            popularity=1,
            key_strengths={}
        ),

        "Minstrel": Tuning(
            name="Minstrel",
            symbol="eAEG#B",
            notes=[64, 45, 52, 56, 59],
            category="historical",
            popularity=1,
            key_strengths={}
        )
    }