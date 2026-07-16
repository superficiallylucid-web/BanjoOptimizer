"""
music.py

Shared music theory utilities for Banjo Optimizer.

This module handles:
- MIDI note names
- pitch classes
- key profiles
- scales
- chord tones

Future modules should import music information from here
instead of duplicating music theory logic.
"""


# ---------------------------------------------------------
# Note names
# ---------------------------------------------------------

NOTE_NAMES = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B"
]


# ---------------------------------------------------------
# Pitch class helpers
# ---------------------------------------------------------

def pitch_class(midi):
    """
    Return pitch class from MIDI number.

    C = 0
    C# = 1
    ...
    B = 11
    """

    return midi % 12



def midi_to_note_name(midi):
    """
    Convert MIDI number to note name.

    Example:

    60 -> C4
    64 -> E4
    67 -> G4
    """

    pc = pitch_class(midi)

    octave = (
        midi // 12
    ) - 1

    return (
        f"{NOTE_NAMES[pc]}"
        f"{octave}"
    )



def pitch_name(pc):
    """
    Convert pitch class to note name.

    Example:

    4 -> E
    7 -> G
    """

    return NOTE_NAMES[pc % 12]



# ---------------------------------------------------------
# Key profiles
# ---------------------------------------------------------

KEY_PROFILES = {


    "C major":
    {
        "tonic": 0,

        "scale":
        [
            0,
            2,
            4,
            5,
            7,
            9,
            11
        ],

        "chord":
        [
            0,
            4,
            7
        ]
    },


    "G major":
    {
        "tonic": 7,

        "scale":
        [
            7,
            9,
            11,
            0,
            2,
            4,
            6
        ],

        "chord":
        [
            7,
            11,
            2
        ]
    },


    "D major":
    {
        "tonic": 2,

        "scale":
        [
            2,
            4,
            6,
            7,
            9,
            11,
            1
        ],

        "chord":
        [
            2,
            6,
            9
        ]
    },


    "A major":
    {
        "tonic": 9,

        "scale":
        [
            9,
            11,
            1,
            2,
            4,
            6,
            8
        ],

        "chord":
        [
            9,
            1,
            4
        ]
    },


    "E minor":
    {
        "tonic": 4,

        "scale":
        [
            4,
            6,
            7,
            9,
            11,
            0,
            2
        ],

        "chord":
        [
            4,
            7,
            11
        ]
    },


    "A minor":
    {
        "tonic": 9,

        "scale":
        [
            9,
            11,
            0,
            2,
            4,
            5,
            7
        ],

        "chord":
        [
            9,
            0,
            4
        ]
    },


    "G minor":
    {
        "tonic": 7,

        "scale":
        [
            7,
            9,
            10,
            0,
            2,
            3,
            5
        ],

        "chord":
        [
            7,
            10,
            2
        ]
    }

}



# ---------------------------------------------------------
# Key functions
# ---------------------------------------------------------

def get_key_profile(key):
    """
    Return scale/chord information for a key.

    Example:

    profile = get_key_profile("E minor")
    """

    return KEY_PROFILES.get(
        key
    )



def key_tonic(key):
    """
    Return tonic pitch class.

    Example:

    E minor -> 4
    """

    profile = get_key_profile(
        key
    )

    if profile:

        return profile["tonic"]

    return None



def scale_contains(key, midi):
    """
    Test whether a MIDI note belongs
    to the scale of the key.
    """

    profile = get_key_profile(
        key
    )

    if not profile:

        return False


    return (
        pitch_class(midi)
        in profile["scale"]
    )



def chord_contains(key, midi):
    """
    Test whether a MIDI note is
    a chord tone of the tonic chord.
    """

    profile = get_key_profile(
        key
    )

    if not profile:

        return False


    return (
        pitch_class(midi)
        in profile["chord"]
    )