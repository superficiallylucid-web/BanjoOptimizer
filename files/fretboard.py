"""
fretboard.py

Shared fretboard math -- finding where a pitch can be played
on a given tuning.

find_positions() and best_position() are extracted from
TuningAnalyzer in optimizer.py, unchanged, as a pure refactor.
They were self-contained methods (no dependency on any other
analyzer state), so moving them here doesn't change behavior --
optimizer.py now imports and calls them exactly as before.

This exists so the melody optimizer and the new chord shape
generator (chord_generator.py) can share one source of truth
for fretboard math instead of duplicating it.
"""


# ---------------------------------------------------------
# Find possible fret positions for a specific pitch
# ---------------------------------------------------------
#
# Extracted unchanged from TuningAnalyzer.find_positions().

def find_positions(midi, open_notes):

    positions = []


    for string_number, open_note in enumerate(open_notes):

        fret = midi - open_note


        if 0 <= fret <= 22:

            positions.append(
                {
                    "string": string_number,
                    "fret": fret,
                    "score": 0
                }
            )


    return positions



# ---------------------------------------------------------
# Choose best fingering position (melody use)
# ---------------------------------------------------------
#
# Extracted unchanged from TuningAnalyzer.best_position().
# This scoring favors middle strings and low frets, which is
# a melody-playing preference specifically -- not reused by
# chord generation, which needs its own scoring (see
# chord_generator.py).

def best_position(positions):

    best = None


    best_score = -999



    for position in positions:


        fret = position["fret"]

        string = position["string"]


        value = 0



        if fret == 0:

            value += 10


        elif fret <= 4:

            value += 8


        elif fret <= 7:

            value += 5


        elif fret <= 12:

            value += 2


        else:

            value -= 3



        # Favor middle melody strings

        if string == 1:

            value += 6


        elif string == 2:

            value += 4


        elif string == 3:

            value += 2



        position["score"] = value


        if value > best_score:

            best_score = value

            best = position


    return best



# ---------------------------------------------------------
# Find valid frets for a target pitch CLASS (chord use)
# ---------------------------------------------------------
#
# New, not extracted -- find_positions() above matches one
# exact MIDI pitch, which is right for melody notes but not
# for chords: a chord tone is a pitch class (e.g. "some C",
# any octave), not one specific pitch. This is the primitive
# chord_generator.py needs: every fret on one open string
# whose resulting pitch class is one of a target set.

def find_frets_for_pitch_classes(
    open_note,
    target_pitch_classes,
    fret_ceiling=7
):
    """
    Return every fret from 0 to fret_ceiling (inclusive) on a
    single string, starting from open_note (a MIDI value),
    whose resulting pitch class is in target_pitch_classes.
    """

    valid_frets = []

    for fret in range(0, fret_ceiling + 1):

        pitch_class = (open_note + fret) % 12

        if pitch_class in target_pitch_classes:

            valid_frets.append(fret)

    return valid_frets



# ---------------------------------------------------------
# Shape string parsing (supports muted strings)
# ---------------------------------------------------------
#
# A chord shape string is one token per string, 4th string to
# 1st. Most tokens are a single fret digit (0-9); a muted
# string is the two characters "--". No delimiter is needed
# between tokens, since a fret is always a single digit in
# this project and "-" never means anything else -- scanning
# left to right, a "-" unambiguously starts a 2-character mute
# token, and any other character is a 1-character fret digit.
#
# This keeps every existing fully-fretted shape (e.g. "2012",
# including every shape already in the verified chord library
# CSVs) in exactly the same format as before -- parse_shape()
# reads those correctly with no muted tokens at all. Only
# shapes that actually mute a string use the longer format.

MUTE = "--"


def parse_shape(shape_text):
    """
    Parse a shape string into a list of one value per string:
    an int fret number, or None for a muted string.
    """

    values = []

    i = 0

    while i < len(shape_text):

        if shape_text[i] == "-":

            values.append(None)

            i += 2

        else:

            values.append(int(shape_text[i]))

            i += 1

    return values


def format_shape(values):
    """
    Inverse of parse_shape(): build a shape string from a list
    of fret numbers / None (muted).
    """

    parts = []

    for value in values:

        if value is None:

            parts.append(MUTE)

        else:

            parts.append(str(value))

    return "".join(parts)


def hand_span(values):
    """
    Fret span of a voicing, ignoring muted AND open strings --
    only the fretted (nonzero, non-muted) notes count toward
    hand stretch. An open string needs no finger and a muted
    string needs no finger either, so neither can contribute
    to how far the hand has to reach.

    Returns 0 if there are no fretted notes at all (e.g. every
    string is open or muted) -- no fingers down means no
    stretch to measure.
    """

    fretted = [
        value for value in values
        if value is not None and value > 0
    ]

    if not fretted:

        return 0

    return max(fretted) - min(fretted)


def average_fret(values):
    """
    Average fret position, ignoring muted AND open strings --
    only fretted notes are averaged. Returns 0.0 if there are
    no fretted notes.
    """

    fretted = [
        value for value in values
        if value is not None and value > 0
    ]

    if not fretted:

        return 0.0

    return sum(fretted) / len(fretted)
