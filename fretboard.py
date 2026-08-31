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

from collections import namedtuple

from music import (
    chord_tones,
    midi_to_note_name,
    note_name_to_pitch_class
)


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

            # 5th-string fretted positions are excluded from
            # melody candidates entirely (per direct instruction):
            # the 5th string is only ever practically playable
            # open (fret 0) -- any fretted position there is
            # difficult enough to be effectively unused, and every
            # pitch reachable on a fretted 5th string is also
            # reachable elsewhere (the 5th string is tuned the
            # same as string 1's own fret 5, so any note playable
            # there is playable on string 1 too). string_number==4
            # is FIFTH_STRING_INDEX (stroke_cycle.py's own existing
            # constant, not redefined here) -- this only ever
            # activates for a caller whose own open_notes includes
            # a 5th string at all; a 4-string open_notes list is
            # completely unaffected. Chord-shape generation never
            # calls find_positions() at all (it uses its own,
            # separate find_frets_for_pitch_classes(), which
            # already excludes the 5th string for the same reason
            # -- this makes melody positions consistent with that
            # existing behavior, not a new restriction).
            if string_number == 4 and fret != 0:

                continue

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

        # BO-99 -- reduced from +6 to +4 (BO-98's own direct A/B
        # confirmation: this is the smallest, narrowest correction
        # to a real, confirmed contextless-decision tension where
        # this string preference could outweigh a much larger
        # fret-band difference, e.g. fret 12/string 1 (score 8)
        # beating fret 5/string 3 (score 7) with no HP/phrase/
        # chord evidence yet to arbitrate between them. Confirmed
        # via exhaustive real-candidate-set testing across every
        # tuning/pitch combination used by this project: this
        # exact value changes only the 2 real cases motivating it
        # -- G4 in C Standard and G4 in Open G -- with zero other
        # effect anywhere else.
        if string == 1:

            value += 4


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
# Shape string parsing (supports muted strings and, since
# BO-21-FOLLOWUP, frets 10 and above)
# ---------------------------------------------------------
#
# A chord shape string is one token per string, 4th string to
# 1st. Most tokens are a single fret digit (0-9); a muted
# string is the two characters "--"; a fret of 10 or higher is
# wrapped in parentheses, e.g. "(10)" or "(12)" -- scanning
# left to right, "-" unambiguously starts a 2-character mute
# token, "(" unambiguously starts a multi-digit fret token
# (read until the matching ")"), and any other character is a
# 1-character fret digit. Parentheses never appeared in any
# shape string before this, so every existing shape (including
# every verified shape in the chord library CSVs) keeps parsing
# exactly as before.
#
# Added because a real melody note can require a high-neck
# fret to be represented at all -- confirmed directly: the
# final chord of a real score needed fret 12 on one string
# (BO-21-FOLLOWUP), which the prior single-digit-only format
# could not encode (format_shape([0,10,10,12]) previously
# produced the corrupted, ambiguous string "0101012").
#
# This keeps every existing fully-fretted shape (e.g. "2012",
# including every shape already in the verified chord library
# CSVs) in exactly the same format as before -- parse_shape()
# reads those correctly with no muted or multi-digit tokens at
# all. Only shapes that actually need one use the longer format.

MUTE = "--"


def parse_shape(shape_text):
    """
    Parse a shape string into a list of one value per string:
    an int fret number, or None for a muted string. Handles
    single-digit frets (e.g. "2"), muted strings ("--"), and
    multi-digit frets wrapped in parentheses (e.g. "(12)") --
    see this module's own notes above.
    """

    values = []

    i = 0

    while i < len(shape_text):

        if shape_text[i] == "-":

            values.append(None)

            i += 2

        elif shape_text[i] == "(":

            close_index = shape_text.index(")", i)

            values.append(int(shape_text[i + 1:close_index]))

            i = close_index + 1

        else:

            values.append(int(shape_text[i]))

            i += 1

    return values


def format_shape(values):
    """
    Inverse of parse_shape(): build a shape string from a list
    of fret numbers / None (muted). A fret of 10 or higher is
    wrapped in parentheses (e.g. "(12)") -- see this module's
    own notes above on why, and on why this never changes the
    output for any single-digit shape.
    """

    parts = []

    for value in values:

        if value is None:

            parts.append(MUTE)

        elif value >= 10:

            parts.append(f"({value})")

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



# ---------------------------------------------------------
# Shape voicing metadata (inversion, top note)
# ---------------------------------------------------------
#
# Shared by chord_generator.py (for shapes it generates) and
# chord_service.py (to enrich verified library shapes, which
# don't otherwise have this metadata -- chord_library.py never
# populates it). One implementation, used by both, so there's
# no risk of the two disagreeing about what a shape's top note
# or inversion is.

INVERSION_NAMES = [
    "Root position",
    "First inversion",
    "Second inversion",
    "Third inversion"
]


def calculate_shape_metadata(
    tuning,
    shape_text,
    root_pc,
    quality_code
):
    """
    Given a tuning, a shape string (e.g. "2012", or "20--2"
    with a muted string), and a chord's root pitch class plus
    quality code, compute (inversion, top_note) for that
    specific voicing.

    - inversion: which chord tone is lowest-sounding (root,
      third, fifth, or seventh), based on its position in
      music.chord_tones()'s interval list -- index 0 is always
      the root.
    - top_note: display name of the highest-sounding pitch
      (e.g. "E4").

    Correctly handles fretted notes, open strings, and muted
    strings -- only strings that are actually sounding (not
    muted) contribute to either calculation, so this works
    the same whether a shape has 3 or 4 sounding strings.

    Returns (None, None) if quality_code isn't recognized by
    music.chord_tones(), or if the shape has no sounding
    strings at all (e.g. every string muted).
    """

    tones = chord_tones(root_pc, quality_code)

    if tones is None:

        return None, None


    melody_strings = tuning.notes[1:]

    values = parse_shape(shape_text)

    pitches = [
        open_note + value
        for open_note, value in zip(melody_strings, values)
        if value is not None
    ]

    if not pitches:

        return None, None


    lowest_pitch = min(pitches)

    highest_pitch = max(pitches)

    lowest_pitch_class = lowest_pitch % 12

    if lowest_pitch_class in tones:

        inversion_index = tones.index(lowest_pitch_class)

    else:

        inversion_index = None


    if (
        inversion_index is not None
        and inversion_index < len(INVERSION_NAMES)
    ):

        inversion = INVERSION_NAMES[inversion_index]

    else:

        inversion = "Unknown inversion"


    top_note = midi_to_note_name(highest_pitch)

    return inversion, top_note



# ---------------------------------------------------------
# Sounding notes by string (melody-occurrence support)
# ---------------------------------------------------------
#
# calculate_shape_metadata() above answers "what's the top
# note / inversion" -- useful chord metadata, but NOT the same
# question as "does this shape contain the melody note, and
# where." A melody note can occur on any sounding string, not
# just the highest one, and a shape can contain the same pitch
# class on more than one string (e.g. a shape sounding
# B-D-G-B has the melody note B on two different strings, and
# neither occurrence has anything to do with top_note, which
# would report the B on top -- or wouldn't, if D or G happened
# to be voiced higher). This section answers the "where does
# this pitch occur" question directly, independent of which
# note is highest.

SoundingNote = namedtuple(
    "SoundingNote",
    ["string_index", "midi", "pitch_class", "name"]
)


def sounding_notes(tuning, shape_text):
    """
    Every actually-sounding note in a shape, one entry per
    non-muted string, in string order (string_index 0 = the
    4th/lowest melody string, matching the shape format --
    same convention as everywhere else in this project).

    Muted strings never appear in the result -- they produce
    no sound, so there's nothing to report for them. Open
    strings count normally.

    Uses the supplied tuning's own open-string notes -- not
    hard-coded to Open G or any other specific tuning.
    """

    melody_strings = tuning.notes[1:]

    values = parse_shape(shape_text)

    notes = []

    for string_index, (open_note, value) in enumerate(
        zip(melody_strings, values)
    ):

        if value is None:

            continue

        midi = open_note + value

        notes.append(
            SoundingNote(
                string_index=string_index,
                midi=midi,
                pitch_class=midi % 12,
                name=midi_to_note_name(midi)
            )
        )

    return notes


def find_melody_occurrences(tuning, shape_text, melody_note):
    """
    Every sounding string in a shape whose pitch class matches
    melody_note -- pitch-class based, the same as everywhere
    else melody matching happens in this project (e.g. "B",
    "B3", and "B5" are all the same match).

    Unlike top_note, this checks EVERY sounding string, not
    just the highest one -- a melody note on an inner voice,
    or doubled across more than one string, is fully reported.
    Muted strings can never match (see sounding_notes).

    Returns a list of SoundingNote (possibly more than one, or
    empty if melody_note doesn't occur anywhere in the shape,
    or can't be parsed).
    """

    target_pitch_class = note_name_to_pitch_class(melody_note)

    if target_pitch_class is None:

        return []

    return [
        note
        for note in sounding_notes(tuning, shape_text)
        if note.pitch_class == target_pitch_class
    ]



# ---------------------------------------------------------
# Melody realization tiers
# ---------------------------------------------------------
#
# find_melody_occurrences() above answers "does this pitch
# class sound anywhere in this shape" -- a binary question.
# This section adds one more level of distinction: WHERE it
# sounds matters too. A melody note that's also the highest-
# sounding note in the shape (the lead voice, matching
# calculate_shape_metadata()'s top_note) is a stronger, more
# direct realization than the same pitch class buried under a
# higher note in an inner voice -- a player following the
# melody hears the top voice most clearly.
#
# This is a per-shape classification, distinct from
# chord_service.diagnose_melody_realization()'s aggregate
# question ("can ANY of these shapes realize this melody note
# at all") -- the two are complementary, not overlapping.

DIRECT_REALIZATION = "DIRECT_REALIZATION"
INDIRECT_REALIZATION = "INDIRECT_REALIZATION"
NO_REALIZATION = "NO_REALIZATION"


def classify_melody_realization(tuning, shape_text, melody_note):
    """
    Classify how well one shape realizes a requested melody
    note:

    - DIRECT_REALIZATION: melody_note is the highest-sounding
      note in the shape (the lead voice) -- the strongest,
      most direct realization.
    - INDIRECT_REALIZATION: melody_note sounds somewhere in the
      shape, but NOT as the highest note -- present, but in an
      inner voice rather than the lead.
    - NO_REALIZATION: melody_note doesn't sound anywhere in
      this shape at all (including if it can't be parsed, or
      the shape has no sounding strings).

    Built entirely from sounding_notes() -- no chord-quality
    information is needed to determine which note is highest,
    so this doesn't require root_pc/quality_code the way
    calculate_shape_metadata() does.
    """

    occurrences = find_melody_occurrences(
        tuning, shape_text, melody_note
    )

    if not occurrences:

        return NO_REALIZATION

    notes = sounding_notes(tuning, shape_text)

    if not notes:

        return NO_REALIZATION

    highest = max(notes, key=lambda note: note.midi)

    target_pitch_class = note_name_to_pitch_class(melody_note)

    if highest.pitch_class == target_pitch_class:

        return DIRECT_REALIZATION

    return INDIRECT_REALIZATION
