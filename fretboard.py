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
