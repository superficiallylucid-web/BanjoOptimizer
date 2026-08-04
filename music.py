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


# ---------------------------------------------------------
# MuseScore TPC (tonal pitch class) decoding
# ---------------------------------------------------------
#
# MuseScore stores note/chord roots as a TPC integer rather
# than a plain pitch class, so that it can tell C# apart from
# Db even though they share a pitch class. TPC walks the
# circle of fifths starting from Fbb; TPC 14 = C natural.
#
# This lets us recover both the note's letter name (with
# sharps/flats) and its underlying 0-11 pitch class.

TPC_LETTERS = ["F", "C", "G", "D", "A", "E", "B"]

BASE_PITCH_CLASS = {
    "F": 5,
    "C": 0,
    "G": 7,
    "D": 2,
    "A": 9,
    "E": 4,
    "B": 11
}


def tpc_to_name(tpc):
    """
    Convert a MuseScore TPC integer to a note name.

    Example:

    14 -> "C"
    20 -> "F#"
    12 -> "Bb"
    """

    letter_index = (tpc + 1) % 7
    alteration = (tpc + 1) // 7 - 2

    letter = TPC_LETTERS[letter_index]

    if alteration > 0:
        suffix = "#" * alteration
    elif alteration < 0:
        suffix = "b" * -alteration
    else:
        suffix = ""

    return f"{letter}{suffix}"


def tpc_to_pitch_class(tpc):
    """
    Convert a MuseScore TPC integer to a 0-11 pitch class.
    """

    letter_index = (tpc + 1) % 7
    alteration = (tpc + 1) // 7 - 2

    letter = TPC_LETTERS[letter_index]

    return (
        BASE_PITCH_CLASS[letter] + alteration
    ) % 12


# ---------------------------------------------------------
# Chord quality lookup
# ---------------------------------------------------------
#
# MuseScore stores chord symbols as a root TPC plus an
# internal "quality code" string (its own chord-description
# shorthand), not the display symbol. This table translates
# the quality codes we've seen in real files into:
#   - intervals: semitones above the root
#   - display: the suffix normally printed after the root
#     (e.g. root "C" + display "maj7" -> "Cmaj7")
#
# Extend this table as new quality codes turn up in other
# scores; MuseScore only uses a bounded set of them.

CHORD_QUALITIES = {

    "": {
        "intervals": [0, 4, 7],
        "display": ""
    },

    "m": {
        "intervals": [0, 3, 7],
        "display": "m"
    },

    "7": {
        "intervals": [0, 4, 7, 10],
        "display": "7"
    },

    "m7": {
        "intervals": [0, 3, 7, 10],
        "display": "m7"
    },

    "maj7": {
        "intervals": [0, 4, 7, 11],
        "display": "maj7"
    },

    "mb5": {
        "intervals": [0, 3, 6],
        "display": "dim"
    },

    "5": {
        "intervals": [0, 7],
        "display": "5"
    },

    "sus2": {
        "intervals": [0, 2, 7],
        "display": "sus2"
    },

    "sus4": {
        "intervals": [0, 5, 7],
        "display": "sus4"
    }

}


def chord_tones(root_pc, quality_code):
    """
    Return the pitch classes in a chord, given a root
    pitch class and a MuseScore quality code.

    Returns None if the quality code isn't recognized yet,
    so callers can decide how to handle unknown chords
    rather than silently guessing.
    """

    quality = CHORD_QUALITIES.get(quality_code)

    if quality is None:

        return None

    return [
        (root_pc + interval) % 12
        for interval in quality["intervals"]
    ]


def chord_display_symbol(root_name, quality_code):
    """
    Build a human-readable chord symbol, e.g. "C" + "m7" -> "Cm7".

    Falls back to showing the raw quality code if it isn't
    in CHORD_QUALITIES yet, so unknown chords are still
    visible instead of silently dropped.
    """

    quality = CHORD_QUALITIES.get(quality_code)

    if quality is None:

        return f"{root_name}({quality_code})"

    return f"{root_name}{quality['display']}"


# ---------------------------------------------------------
# Tuning symbol from raw string data
# ---------------------------------------------------------

def tuning_symbol_from_notes(notes):
    """
    Build a tuning symbol string (e.g. "gDGBD") from a list
    of open-string MIDI values, ordered 5th string to 1st.

    This is the ground truth for what a file is *actually*
    tuned to — as opposed to whatever a filename or title
    happens to claim. Always prefer this over parsing a
    filename.
    """

    if not notes:

        return ""

    letters = [pitch_name(pitch_class(midi)) for midi in notes]

    fifth_string = letters[0].lower()

    rest = "".join(letters[1:])

    return f"{fifth_string}{rest}"