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
# Choose a compact simultaneous voicing (BO-133.5)
# ---------------------------------------------------------
#
# For genuine multi-note melody events (two or more pitches
# sounding at the same onset, e.g. a real dyad within the
# melody line itself -- confirmed real, distinct from a chord
# symbol, via BO-133.3's own investigation). v1 scope: exactly
# two simultaneous pitches; a third or more is out of scope
# (see this function's own docstring below).

def _best_same_octave_combination(pitches, open_notes):
    """
    The best playable, different-string pairing for these exact
    pitches, no octave consideration at all. Returns (span,
    position_a, position_b) or None if no valid pairing exists.
    Factored out so choose_simultaneous_positions() can reuse it
    identically for both the source pitches and any octave-
    shifted alternative -- one search, not a parallel copy.

    BO-133.5 Part A -- "best" balances fret span AND absolute
    fret comfort together, reusing the existing fret-band values
    (fretboard._fret_band_value(), the same tiers best_position()
    itself uses -- not a new, separate scale) rather than
    minimizing span alone. Confirmed directly against the real
    Gamboge case that pure span-minimization picks a technically-
    zero-span but musically poor high-neck voicing (both notes
    at fret 17) over a genuinely comfortable, still-compact
    voicing one fret apart at frets 9/10 -- span alone can't
    distinguish "close together" from "close together AND
    reasonably placed". combined_score = the sum of both
    positions' own fret-band value, minus 1 point per fret of
    span (SPAN_PENALTY_WEIGHT -- deliberately the same unit scale
    as the fret-band values themselves, not an arbitrarily large
    or small number chosen to force one particular case). The
    combination with the HIGHEST combined_score wins; span (this
    tuple's own first element) is still returned and still used
    by choose_simultaneous_positions()'s own outer "is the
    original good enough to skip octave search" gate, which
    remains a direct span comparison against
    playability.MAX_ACCEPTABLE_SPAN, unchanged by this addition.
    """

    positions_a = find_positions(pitches[0], open_notes)

    positions_b = find_positions(pitches[1], open_notes)

    SPAN_PENALTY_WEIGHT = 1

    valid_combinations = []

    for position_a in positions_a:

        for position_b in positions_b:

            if position_a["string"] == position_b["string"]:

                continue

            span = abs(position_a["fret"] - position_b["fret"])

            combined_score = (
                _fret_band_value(position_a["fret"])
                + _fret_band_value(position_b["fret"])
                - SPAN_PENALTY_WEIGHT * span
            )

            valid_combinations.append(
                (span, combined_score, position_a, position_b)
            )

    if not valid_combinations:

        return None

    valid_combinations.sort(
        key=lambda combination: (
            -combination[1],
            min(
                combination[2]["fret"], combination[3]["fret"]
            )
        )
    )

    return valid_combinations[0]


def _positions_from_fd_anchor(
    pitches, open_notes, fd_anchor_shape_values
):
    """
    BO-135 -- check whether the already-selected chord shape at
    this exact onset (fd_anchor_shape_values, BO-internal parsed
    values, e.g. from _select_chord_shape_for_harmony()) already
    sounds both of the two simultaneous melody pitches, each on
    its own distinct string.

    Confirmed real, direct root cause (BO-135's own investigation
    report): choose_simultaneous_positions() previously searched
    for a compact voicing entirely independently of any chord
    shape already selected for this same onset, even when that
    shape already, correctly contained both melody pitches --
    producing a TAB that didn't match the FD despite a matching,
    already-known-good representation existing. This reuses the
    chord shape's own already-selected positions exactly, rather
    than searching for a new, separate compact voicing that may
    happen to disagree with it.

    Matched by PITCH CLASS (mod 12), not exact MIDI value.
    Confirmed directly against the real Gamboge case this was
    built for: chord selection had already, independently chosen
    a shape voicing the melody's own D a different octave (62)
    than the source melody note's own raw pitch (74) -- same
    pitch class, different octave, consistent with this whole
    function's own already-established BO-133.5-FOLLOWUP octave-
    adjustment philosophy elsewhere. Matching by exact MIDI value
    here would have meant this anchor never applied to the exact
    case it exists to fix. The returned position's own "pitch"
    is the anchor's own actual sounding pitch (e.g. 62), not the
    original melody pitch passed in (e.g. 74) -- the whole point
    is for the TAB to represent the same, already-selected chord
    voicing the FD does, not merely to find a differently-voiced
    position for the original pitch.

    Returns a list of exactly two position dicts (same
    {"pitch", "string", "fret", "score"} shape this module's own
    choose_simultaneous_positions() returns), in the same order
    as `pitches`, if and only if the anchor shape sounds a note
    of BOTH pitches' own pitch classes, on two DIFFERENT strings.
    Returns None otherwise (the anchor doesn't cover one or both
    pitch classes, or would require the same physical string for
    both) -- callers should fall back to the existing independent
    search in that case, not treat this as an error.
    """

    used_strings = set()

    positions = []

    for pitch in pitches:

        match = None

        for string_index, fret in enumerate(
            fd_anchor_shape_values
        ):

            if fret is None:

                continue

            if string_index >= len(open_notes):

                continue

            if string_index in used_strings:

                continue

            sounding_pitch = open_notes[string_index] + fret

            if sounding_pitch % 12 == pitch % 12:

                match = {
                    "string": string_index,
                    "fret": fret,
                    "score": 0,
                    "pitch": sounding_pitch
                }

                break

        if match is None:

            return None

        used_strings.add(match["string"])

        positions.append(match)

    return positions


def choose_simultaneous_positions(
    pitches, open_notes, fd_anchor_shape_values=None
):
    """
    Given exactly two simultaneous melody pitches, choose a
    compact, physically playable pair of positions -- one per
    pitch, each reusing the existing, unmodified
    find_positions() candidate source.

    BO-135 -- fd_anchor_shape_values: optional, the already-
    selected chord shape's own parsed values (BO-internal order)
    at this exact onset, if one exists. When provided and it
    genuinely sounds both pitches on two different strings, its
    own positions are used directly -- see
    _positions_from_fd_anchor()'s own docstring for the full
    reasoning. Falls through to the existing, unmodified
    independent search below whenever no anchor is given, or the
    anchor doesn't cover both pitches -- this is strictly
    additive; every case this function already handled before
    BO-135 is completely unaffected.

    Two notes can never sound from the same physical string at
    once, so any combination pairing both pitches onto the same
    string is rejected outright, not merely deprioritized -- the
    only hard rejection here, since it's a genuine physical
    impossibility rather than a preference.

    Among the remaining, physically playable combinations,
    always prefers the smallest fret span -- deliberately NOT
    hard-capped against playability.MAX_ACCEPTABLE_SPAN when NO
    alternative exists (confirmed directly against the real
    Gamboge case that a genuine 2-note melodic interval can
    require a real span every same-octave combination exceeds --
    e.g. midi 57/74, a 17-semitone interval, where the closest
    same-octave pairing in A Minor tuning is still a span of 5).

    BO-133.5-FOLLOWUP -- octave consideration: when the best
    SAME-octave combination's own span exceeds
    playability.MAX_ACCEPTABLE_SPAN (reusing this project's own
    existing "genuinely compact" threshold, not a new number),
    also tries exactly one of the two pitches shifted by exactly
    one octave (+12 or -12), the other left at its own written
    pitch -- matching the specific, bounded alternatives named
    directly (BO-133.5-FOLLOWUP's own report): shift the first
    pitch, or shift the second, in either direction. This is
    deliberately narrow, not a general search across every
    octave/every note -- exactly one note, exactly one octave,
    only ever considered as a mechanism for making THIS
    simultaneous pair playable as a compact voicing, never
    applied to an ordinary single-note melody event at all.

    An octave-shifted alternative is only ever PREFERRED over the
    original, same-octave result when its own best span is
    ITSELF within MAX_ACCEPTABLE_SPAN (the same "genuinely
    compact enough to be worth it" bar, not merely "somewhat
    smaller than before") -- among multiple qualifying
    alternatives, the smallest span wins; ties broken the same
    way as the same-octave search. If no octave-shifted
    alternative qualifies, the original, same-octave result is
    kept even though it isn't compact -- consistent with this
    function's own existing "never return None when a real,
    playable combination exists" philosophy elsewhere.

    Returns a list of exactly two position dicts (each
    {"pitch", "string", "fret", "score"} -- "pitch" added by
    BO-133.5-FOLLOWUP so callers can see the ACTUAL pitch used
    for each position, which may differ from the corresponding
    entry in `pitches` if an octave shift was applied; "string"/
    "fret"/"score" remain the same shape find_positions() itself
    returns), in the same order as `pitches`, or None if no
    valid combination exists at all in any octave considered --
    callers should treat None as "no compact simultaneous
    voicing available", not an error.

    v1 scope only: len(pitches) must be exactly 2. Returns None
    for any other count -- a genuine 3+-note simultaneous event
    is out of scope (see BO-133.5's own report).
    """

    if len(pitches) != 2:

        return None

    if fd_anchor_shape_values is not None:

        anchor_positions = _positions_from_fd_anchor(
            pitches, open_notes, fd_anchor_shape_values
        )

        if anchor_positions is not None:

            return anchor_positions

    from playability import MAX_ACCEPTABLE_SPAN

    same_octave_best = _best_same_octave_combination(
        pitches, open_notes
    )

    best_span = (
        same_octave_best[0] if same_octave_best else None
    )

    best_score = (
        same_octave_best[1] if same_octave_best else None
    )

    best_combination = same_octave_best

    best_pitches = pitches

    if best_span is None or best_span > MAX_ACCEPTABLE_SPAN:

        for shifted_index in (0, 1):

            for octave_shift in (12, -12):

                candidate_pitches = list(pitches)

                candidate_pitches[shifted_index] += octave_shift

                candidate_best = _best_same_octave_combination(
                    candidate_pitches, open_notes
                )

                if candidate_best is None:

                    continue

                if candidate_best[0] > MAX_ACCEPTABLE_SPAN:

                    continue

                # BO-133.5 Part A -- compare octave-shifted
                # alternatives to each other, and to the
                # original, using the same combined fret-band-
                # comfort-minus-span score used inside
                # _best_same_octave_combination() itself, not
                # raw span -- consistent with this whole
                # correction's own point (span alone can't tell
                # "close together" apart from "close together AND
                # reasonably placed").
                if (
                    best_combination is None
                    or best_score is None
                    or candidate_best[1] > best_score
                ):

                    best_span = candidate_best[0]

                    best_score = candidate_best[1]

                    best_combination = candidate_best

                    best_pitches = candidate_pitches

    if best_combination is None:

        return None

    _, _, best_a, best_b = best_combination

    return [
        {**best_a, "pitch": best_pitches[0]},
        {**best_b, "pitch": best_pitches[1]}
    ]




# ---------------------------------------------------------
# Choose best fingering position (melody use)
# ---------------------------------------------------------
#
# Extracted unchanged from TuningAnalyzer.best_position().
# This scoring favors middle strings and low frets, which is
# a melody-playing preference specifically -- not reused by
# chord generation, which needs its own scoring (see
# chord_generator.py).

def _fret_band_value(fret):
    """
    The graduated fret-band comfort value used by
    best_position() -- extracted (BO-133.5 Part A) so it can be
    reused by fretboard.choose_simultaneous_positions() too,
    rather than duplicating these same tier boundaries a second
    time. Pure refactor of what was previously inline in
    best_position() -- confirmed via the full regression suite
    this produces byte-identical output to before the
    extraction.

    Higher value = more comfortable/lower on the neck. See
    best_position()'s own docstring/history for why these
    specific tier boundaries and values were chosen (0, <=4,
    <=7, <=12, <=17, else), including BO-133.1's own addition of
    the <=17 tier.
    """

    if fret == 0:

        return 10

    elif fret <= 4:

        return 8

    elif fret <= 7:

        return 5

    elif fret <= 12:

        return 2

    elif fret <= 17:

        return 0

    else:

        return -3


def best_position(positions):

    best = None


    best_score = -999



    for position in positions:


        fret = position["fret"]

        string = position["string"]


        value = _fret_band_value(fret)



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
