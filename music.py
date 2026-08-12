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


# ---------------------------------------------------------
# Note name to pitch class
# ---------------------------------------------------------
#
# Inverse of pitch_name(): needed for melody-note matching,
# where a note name (e.g. "E", "E4", from a ChordShape's
# top_note or a caller's melody note) needs to be compared by
# pitch class. Nothing like this existed before -- everywhere
# else in the project only ever went pitch-class-to-name, never
# the other direction.

FLAT_TO_SHARP = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
    "Cb": "B",
    "Fb": "E"
}


def note_name_to_pitch_class(name):
    """
    Parse a note name into a 0-11 pitch class. An octave digit,
    if present, is ignored -- e.g. "E", "E4", and "E5" all
    return the same pitch class, since pitch-class matching
    (not octave-specific matching) is what melody-note matching
    needs.

    Returns None if the name can't be parsed, so callers can
    treat that as "no identifiable note" rather than guessing.
    """

    if not name:

        return None

    letter = name[0].upper()

    if letter not in "ABCDEFG":

        return None

    index = 1

    accidental = ""

    while index < len(name) and name[index] in "#b":

        accidental += name[index]

        index += 1

    remainder = name[index:]

    if remainder and not remainder.lstrip("-").isdigit():

        # Anything after the letter/accidental must be an
        # octave number (or nothing) -- "garbage" isn't a note
        # name just because it starts with a valid letter.
        return None

    base = letter + accidental

    base = FLAT_TO_SHARP.get(base, base)

    if base in NOTE_NAMES:

        return NOTE_NAMES.index(base)

    return None


# ---------------------------------------------------------
# Voicing quality: root presence and defining-tone coverage
# ---------------------------------------------------------
#
# Distinguishes "is this a valid collection of chord tones"
# (chord_tones() already answers that) from "how strongly does
# this specific set of sounding notes establish the requested
# chord." A shape can be fully valid and fully playable while
# still being a weak representation of the chord it's named
# for -- e.g. a rootless voicing containing only one generic
# tone, duplicated across strings.
#
# This never rejects anything -- it's a ranking signal, not a
# filter. A rootless voicing that covers a chord's defining
# tones is explicitly a legitimate, often-used voicing choice
# (e.g. a rootless dominant-7th built on the 3rd and 7th), not
# something to discard.

ROOT_PRESENT = "ROOT_PRESENT"
ROOTLESS_STRONG = "ROOTLESS_STRONG"
ROOTLESS_WEAK = "ROOTLESS_WEAK"


def defining_tones(root_pc, quality_code):
    """
    Which chord tones (besides the root) most establish a
    chord's identity -- derived structurally from the quality's
    own interval list in CHORD_QUALITIES, not a separate,
    hardcoded per-chord table.

    Rule: every non-root tone EXCEPT a perfect 5th above the
    root (interval 7) is "defining." The perfect 5th is present
    in nearly every quality this project supports and is
    routinely altered or dropped in real voicings without
    threatening the chord's identity (jazz guide-tone voicings
    regularly omit it). Everything else -- the 3rd (major or
    minor), a sus2/sus4 substitute tone, any kind of 7th, or an
    ALTERED 5th (a diminished triad's flat 5 is interval 6, not
    7, so it's never excluded) -- is what actually distinguishes
    one quality from another.

    Exception: a quality with no non-root tone besides the
    perfect 5th (i.e. "5", a power chord) falls back to
    treating that 5th as defining after all -- with only two
    notes total, excluding it would leave nothing defining at
    all, which isn't useful.

    Returns None if quality_code isn't recognized.
    """

    tones = chord_tones(root_pc, quality_code)

    if tones is None:

        return None

    non_root = tones[1:]

    perfect_fifth = (root_pc + 7) % 12

    defining = [
        tone for tone in non_root
        if tone != perfect_fifth
    ]

    if not defining:

        defining = non_root

    return defining


def classify_voicing_quality(
    root_pc,
    quality_code,
    sounding_pitch_classes
):
    """
    Classify how strongly a set of actually-sounding pitch
    classes establishes the requested chord. Distinct from
    playability (can it be fingered) and from bare chord-tone
    validity (is every sounding note technically part of the
    chord). Never rejects anything -- see module notes above.

    Returns (category, score):

    - ROOT_PRESENT: the root itself is sounding. Always the
      strongest category regardless of what else is present --
      a voicing that states its own root is never ambiguous
      about which chord it is.
    - ROOTLESS_STRONG: the root is absent, but every defining
      tone (see defining_tones()) IS present -- e.g. a rootless
      dominant-7th voicing that still has both the 3rd and 7th.
    - ROOTLESS_WEAK: the root is absent AND at least one
      defining tone is missing too -- the weakest, most
      ambiguous case.

    The numeric score adds a small bonus per additional
    DISTINCT chord tone covered beyond the category itself, so
    two voicings in the same category aren't scored as
    identical -- e.g. a rootless-strong voicing that also
    includes the 5th ranks above a rootless-strong voicing
    that's just the bare defining tones. Duplicate notes on
    multiple strings never inflate this -- only distinct pitch
    classes are counted.

    Returns (None, 0.0) if quality_code isn't recognized.
    """

    tones = chord_tones(root_pc, quality_code)

    if tones is None:

        return None, 0.0

    defining = defining_tones(root_pc, quality_code)

    distinct = frozenset(sounding_pitch_classes)

    has_root = root_pc in distinct

    if has_root:

        category = ROOT_PRESENT

        base_score = 15.0

    elif frozenset(defining).issubset(distinct):

        category = ROOTLESS_STRONG

        base_score = 6.0

    else:

        category = ROOTLESS_WEAK

        base_score = 0.0

    coverage_bonus = len(distinct & frozenset(tones)) * 2.0

    return category, base_score + coverage_bonus



# ---------------------------------------------------------
# Quality code -> chord library display name
# ---------------------------------------------------------
#
# chord_tones() and CHORD_QUALITIES use one naming convention
# for chord quality ("", "m", "maj7", "mb5", ...); the verified
# chord_library.py CSV data uses a different one for its
# Quality column ("Major", "minor", "Maj 7", "dim", ...) --
# confirmed directly against the real CSV. Nothing has bridged
# these two before now; anywhere a chord is extracted from a
# real score (root_pc + quality_code, from Harmony) needs to
# be looked up against the verified library, this mapping is
# the missing link.
#
# Deliberately only covers quality codes CHORD_QUALITIES
# already recognizes -- not a new theory system, just naming
# reconciliation for what already exists on both sides.

QUALITY_CODE_TO_DISPLAY_NAME = {
    "": "Major",
    "m": "minor",
    "7": "Dom 7",
    "m7": "min 7",
    "maj7": "Maj 7",
    "mb5": "dim",
    "5": "5 (no 3rd)",
    "sus2": "sus2",
    "sus4": "sus4",
}


def quality_code_to_display_name(quality_code):
    """
    Return the chord_library.py CSV-style display name for a
    quality_code (e.g. "maj7" -> "Maj 7"), or None if the code
    isn't recognized. A None result isn't an error -- callers
    should treat it the same as any other "no data available
    for this chord" case (e.g. pass it straight through to
    ChordService, which will simply find no verified/generated
    shapes for an unrecognized quality).
    """

    return QUALITY_CODE_TO_DISPLAY_NAME.get(quality_code)