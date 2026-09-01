"""
models.py

Core data models for Banjo Optimizer.
"""

from dataclasses import dataclass, field

from music import (
    midi_to_note_name,
    pitch_class,
)


# ---------------------------------------------------------
# Harmony model
# ---------------------------------------------------------

@dataclass
class Harmony:
    """
    Represents one chord symbol found in the score
    (e.g. "Cmaj7" at measure 2).

    beat: position within the measure, in quarter-note beats
        (0.0 = the downbeat), computed by accumulating note/
        rest durations through the voice -- see
        parser.read_harmonies(). Does not account for tuplets
        (none have been seen in any file this project has
        parsed yet -- see parser._duration_value()); a score
        using them would see beat drift after the tuplet, not
        an exact value.

    shape: the actual fingering the player used at this chord
        occurrence, read directly from the score's own
        <FretDiagram> data (when present) -- ground truth for
        what was actually played, not inferred or generated.
        Uses the same 4-character shape-string format as
        elsewhere in this project (fretboard.parse_shape/
        format_shape): one character per string, "0" for open,
        a digit for a fretted position, matching the real
        MuseScore data this project has seen so far (no muted-
        string markers have been observed in <FretDiagram>
        data; if one is ever seen, it isn't handled yet -- see
        parser.read_harmonies()). Empty string ("") if no
        FretDiagram was found at this occurrence -- how common
        that is varies by score; the My Favorite Things
        arrangement this was developed against happens to have
        one for every chord symbol, but that's this file's own
        thoroughness, not something to assume of every score.

        This chord symbol tells you what the arranger intended;
        this shape tells you what they actually played. They
        are deliberately two different pieces of information --
        the same symbol can have different shapes at different
        occurrences (confirmed with real data: "Em" appears as
        both "0220" and "0223" in the same score).
    """

    measure: int

    root_pc: int

    quality_code: str

    symbol: str

    tones: list[int] = field(default_factory=list)

    shape: str = ""

    beat: float = 0.0


# ---------------------------------------------------------
# Note model
# ---------------------------------------------------------

@dataclass
class Note:
    """
    Represents one melody note.
    """

    midi: int

    measure: int = 0

    beat: float = 0.0

    duration: float = 0.0

    voice: int = 0

    @property
    def name(self):
        return midi_to_note_name(self.midi)

    @property
    def pitch_class(self):
        return pitch_class(self.midi)

    def __str__(self):
        return self.name


# ---------------------------------------------------------
# Measure model
# ---------------------------------------------------------

@dataclass
class Measure:
    number: int

    notes: list[Note] = field(default_factory=list)

    def add_note(self, note: Note):
        self.notes.append(note)


# ---------------------------------------------------------
# Score model
# ---------------------------------------------------------

@dataclass
class Score:
    title: str = "Unknown Title"

    composer: str = ""

    key: str = "Unknown"

    key_confidence: float = 0.0

    time_signature: str = "Unknown"

    notes: list[Note] = field(default_factory=list)

    measures: list[Measure] = field(default_factory=list)

    harmonies: list[Harmony] = field(default_factory=list)

    def add_note(self, note: Note):
        self.notes.append(note)

    def add_measure(self, measure: Measure):
        self.measures.append(measure)

    def add_harmony(self, harmony: Harmony):
        self.harmonies.append(harmony)

    def melody_note_for_harmony(self, harmony):
        """
        Return the MIDI pitch of the melody note associated
        with a chord occurrence.

        Both Note.beat and Harmony.beat are now populated by
        the parser (accumulated note/rest durations through the
        voice -- see parser.read_staff_notes()/read_harmonies()),
        so this first looks for a note at the EXACT same
        (measure, beat) as the harmony -- beats are rounded to
        4 decimal places on the way in, so this is a direct
        equality check, not a fuzzy one.

        Falls back to the first note in the same measure (the
        old, purely measure-level behavior) only if no note
        shares the harmony's exact beat -- e.g. a chord change
        that doesn't line up with a new note onset. That
        fallback is still an approximation, same as before;
        the exact-beat path is the real improvement here.

        Returns None if there's no note in the measure at all.
        """

        for note in self.notes:

            if (
                note.measure == harmony.measure
                and note.beat == harmony.beat
            ):

                return note.midi

        for note in self.notes:

            if note.measure == harmony.measure:

                return note.midi

        return None

    @property
    def note_count(self):
        return len(self.notes)

    @property
    def lowest_note(self):
        if not self.notes:
            return None

        return min(self.notes, key=lambda n: n.midi)

    @property
    def highest_note(self):
        if not self.notes:
            return None

        return max(self.notes, key=lambda n: n.midi)

    @property
    def range_description(self):
        if not self.notes:
            return "Unknown"

        return f"{self.lowest_note.name} - {self.highest_note.name}"


# ---------------------------------------------------------
# Tuning model
# ---------------------------------------------------------

@dataclass
class Tuning:
    name: str

    symbol: str

    notes: list[int]

    category: str

    popularity: int

    key_strengths: dict = field(default_factory=dict)

    # Practical setup information

    base_tuning: str | None = None

    capo: int = 0

    fifth_string_note: str | None = None


# ---------------------------------------------------------
# Optimizer result
# ---------------------------------------------------------

@dataclass
class TuningResult:
    """
    One recommended tuning, with its explanation broken into
    categories a player can actually use to decide between
    options -- rather than one flat list of reasons.

    advantages: what's genuinely distinguishing about this
        tuning (shared_features has already been factored out)
    tradeoffs: downsides specific to this tuning (e.g. notes
        that require difficult positions); empty if none
    shared_features: characteristics this tuning has in common
        with the other recommendations it was shown alongside.
        Populated by a group-level step (see recommendations.py),
        not by scoring a single tuning in isolation.
    confidence: score gap to this result's nearest neighbor in
        the group it's shown alongside -- a small value means a
        genuine near-tie with another shown option. Populated by
        a group-level step (see recommendations.apply_confidence()),
        same as shared_features; None until that step runs, or
        for a single-result group with nothing to compare
        against.
    """

    name: str

    symbol: str

    category: str = ""

    score: float = 0.0

    advantages: list[str] = field(default_factory=list)

    tradeoffs: list[str] = field(default_factory=list)

    shared_features: list[str] = field(default_factory=list)

    confidence: float | None = None

    # BO-48 -- Chord/FD quality and unplayable-note metrics,
    # kept as SEPARATE fields alongside the existing, unchanged
    # `score` (the raw melody/Playing-Model score, still the
    # value every pre-existing caller/test/report reads). See
    # optimizer.py's own module-level docstring for the full
    # combination formula and why these are separate concepts.

    # Raw mean of max(0, working_fret - 7) across this tuning's
    # own real chord onsets (the exact BO-43/44/46 definition,
    # reused unmodified). 0.0 for a song with no harmony data.
    avg_awkwardness: float = 0.0

    # avg_awkwardness normalized to [0, 1] via a FIXED reference
    # range (see optimizer.py's own MAX_AWKWARDNESS_REFERENCE),
    # NOT the current candidate set's own min/max -- this is
    # what BO-47 found candidate-set-dependent min-max gets
    # wrong, and what this field is specifically designed to
    # avoid. 1.0 = as comfortable as the reference range allows,
    # 0.0 = at or beyond it. Independent of which other tunings
    # are being compared alongside this one.
    chord_fd_quality: float = 1.0

    # How many of this tuning's own melody notes have NO valid
    # fret/string position at all (find_positions() returns
    # empty) -- a hard playability failure, not an awkwardness-
    # of-comfortable-positions question. Real example: My
    # Favorite Things / Old G, 18 notes below the lowest open
    # string.
    unplayable_note_count: int = 0

    unplayable_note_proportion: float = 0.0

    # BO-131.4 -- mean analyze_chord_shape_playability().score
    # across this tuning's own real chord occurrences, evaluated
    # on the EXACT shape _select_chord_shape_for_harmony() itself
    # selects (the same call chord_fd_quality_bonus() already
    # makes for avg_awkwardness, reused rather than a second,
    # independent selection). Unlike chord_fd_quality above, this
    # does NOT pass through analyze_tuning_playing_model() at
    # all, so it carries none of that path's own melody-
    # combination contribution -- a measurement of chord-shape
    # quality alone, on the shapes BO would actually generate.
    #
    # Deliberately NOT yet part of combined_score or any existing
    # weight (CHORD_FD_INFLUENCE, PLAYING_MODEL_WEIGHT) -- BO-131
    # scoped this as a measurement correction only; whether/how
    # to weight it into the actual ranking is a separate,
    # subsequent decision. 0.0 for a song with no harmony data or
    # no chord shape selectable for this tuning (matching
    # avg_awkwardness's own "nothing to measure" convention).
    avg_generated_chord_playability: float = 0.0

    # The score `analyze()` actually sorts and recommends by --
    # `score` (melody) blended with `chord_fd_quality` at
    # CHORD_FD_INFLUENCE, then the separate unplayable-note
    # penalty applied on top. Equal to `score` when this
    # tuning's own group was never combined (e.g. a caller that
    # only ever calls score_tuning() directly, bypassing
    # analyze()'s own group-level combination step) -- callers
    # should prefer this field for ranking/display once
    # analyze() has run, and `score` for melody-only diagnostics.
    combined_score: float = 0.0


# ---------------------------------------------------------
# Chord shape model
# ---------------------------------------------------------

@dataclass
class ChordShape:
    """
    One playable chord shape from a chord shape library CSV
    (e.g. chord_library/banjo_chord_library - gDGBD Chord
    Shapes.csv).

    shape is a string of one fret number per string, ordered
    4th string to 1st string (the 5th/drone string isn't
    included) -- e.g. "2012" for a C major shape in gDGBD.
    This matches the 4-string fret format already seen in
    MuseScore FretDiagram data.

    Not yet connected to scoring or recommendations -- this
    is purely a data model for loading and looking up chord
    shapes.

    source: where this particular ChordShape instance came
        from -- "verified" (from a chord_library CSV row),
        "generated" (from chord_generator.py's fretboard
        search), or "unknown" (default, for any code that
        hasn't set it). Set by chord_service.py when it merges
        library and generator results; chord_library.py and
        chord_generator.py don't set this themselves. Distinct
        from `verified`, which describes the shape's own
        confirmation status, not which system produced it.

    inversion: which chord tone is lowest-sounding in this
        specific voicing -- "Root position", "First
        inversion", "Second inversion", or "Third inversion"
        (for 7th chords). Set by chord_generator.py for the
        shapes it produces. Empty string ("") for shapes from
        elsewhere (e.g. chord_library.py) that haven't had
        this computed -- an empty value means "not yet
        determined", not "root position".
    top_note: the highest-pitched note actually sounding in
        this voicing (e.g. "E4"), also set by
        chord_generator.py. Laying groundwork for future
        melody-note matching -- not used by scoring or
        ranking yet.
    average_fret: average of only the FRETTED strings in this
        voicing (open and muted strings excluded). For ranking
        within chord_generator.py only.
    hand_span: highest fretted note minus lowest fretted note
        in this voicing, ignoring open and muted strings --
        e.g. a single fretted note (everything else open/muted)
        has a span of 0, not a stretch.
    generator_score: chord_generator.py's own playability
        estimate for this specific voicing, kept for reference/
        debugging. Distinct from playability.py's score, which
        is a separate, later evaluation. Also distinct from
        voicing_quality_score below -- this one is purely about
        physical playability (span, open strings, etc.), not
        about how well the sounding notes establish the chord.
    voicing_quality_category: one of "ROOT_PRESENT",
        "ROOTLESS_STRONG", "ROOTLESS_WEAK", or "" (not yet
        computed). See music.classify_voicing_quality() for the
        exact rule. Never used to reject a shape -- a rootless
        voicing covering a chord's defining tones is a
        legitimate voicing choice, not an invalid one.
    voicing_quality_score: numeric score behind the category
        above, used as one ranking input alongside
        generator_score. Higher is a stronger representation of
        the requested chord.
    """

    tuning: str

    root: str

    quality: str

    shape: str

    comfort_code: int | None = None

    comfort_explanation: str = ""

    comments: str = ""

    verified: bool | None = None

    source: str = "unknown"

    inversion: str = ""

    top_note: str = ""

    average_fret: float = 0.0

    hand_span: int = 0

    generator_score: float = 0.0

    voicing_quality_category: str = ""

    voicing_quality_score: float = 0.0


# ---------------------------------------------------------
# Playability filter result
# ---------------------------------------------------------

@dataclass
class PlayabilityResult:
    """
    Result of running a chord shape through the playability
    filter (playability.py).

    Deliberately minimal for this first version -- accepted /
    reason / warnings / score is the whole API surface. Meant
    to be easy to extend later (e.g. a per-rule breakdown)
    without breaking existing callers, since every field but
    accepted has a default.
    """

    accepted: bool

    reason: str = ""

    warnings: list[str] = field(default_factory=list)

    score: int = 0


# ---------------------------------------------------------
# Melody realization diagnostic
# ---------------------------------------------------------
#
# Distinguishes "is the melody note theoretically a chord tone"
# from "does a playable shape actually put it somewhere usable"
# -- two different questions the My Favorite Things
# investigation showed get conflated easily. See
# chord_service.diagnose_melody_realization() for the function
# that produces these.

@dataclass
class MelodyRealizationMatch:
    """
    One playable shape's occurrence of the requested melody
    note -- which shape, where on it, and what actually sounds
    there.
    """

    shape: str

    source: str

    voicing_quality_category: str

    string_index: int

    fret: int

    sounding_note: str


@dataclass
class MelodyRealizationDiagnostic:
    """
    Result of diagnose_melody_realization(): whether a melody
    note is a chord tone of the written chord, and separately,
    whether any of the given playable shapes actually realizes
    it. Never used to pick a replacement chord -- purely
    diagnostic, feeding future chord-substitution work rather
    than doing any of it here.

    category is one of chord_service.py's
    CHORD_TONE_AND_USABLE_VOICING / CHORD_TONE_BUT_NO_USABLE_VOICING
    / NOT_A_CHORD_TONE.
    """

    category: str

    root: str

    quality_code: str

    melody_note: str

    matches: list[MelodyRealizationMatch] = field(
        default_factory=list
    )


# ---------------------------------------------------------
# Shape selection result
# ---------------------------------------------------------
#
# Result of chord_service.select_shape_for_melody(): the
# single best shape for one chord+melody occurrence, paired
# with how well it actually realizes the melody and the
# existing aggregate diagnosis (whether ANY shape could realize
# it at all). This is architecture for future chord-
# substitution work, not substitution logic itself -- it makes
# "no shape can do this" an explicit, checkable fact instead of
# silently returning a shape that doesn't really work.

@dataclass
class ShapeSelectionResult:
    """
    selected_shape: the best available ChordShape, or None if
        get_shapes_for_melody() returned nothing at all (e.g.
        an unrecognized chord quality) -- distinct from a
        recognized chord with no melody-realizing shape, which
        still returns a selected_shape (the best playable one
        available), just with a low realization_tier and a
        diagnosis that says so.
    realization_tier: one of fretboard.py's DIRECT_REALIZATION
        / INDIRECT_REALIZATION / NO_REALIZATION, for
        selected_shape specifically. "" if selected_shape is
        None.
    diagnosis: the existing MelodyRealizationDiagnostic (see
        chord_service.diagnose_melody_realization()) -- the
        aggregate answer for whether melody_note is even a
        theoretical chord tone, and whether ANY shape in the
        full ranked list realizes it, not just the one chosen
        here.
    all_shapes_ranked: the full ranked list selected_shape came
        from (see get_shapes_for_melody()), kept for deeper
        diagnostics -- callers that just want the concise
        answer should look at selected_shape/realization_tier/
        diagnosis.category, not this list.
    """

    selected_shape: ChordShape | None

    realization_tier: str

    diagnosis: MelodyRealizationDiagnostic

    all_shapes_ranked: list = field(default_factory=list)


# ---------------------------------------------------------
# Chord vocabulary analysis (tuning comparison evidence)
# ---------------------------------------------------------
#
# Evidence-gathering for comparing how well two tunings serve
# the same score's chord vocabulary -- e.g. aDADE vs aEADE on
# a specific arrangement. Deliberately just evidence: no score,
# no "winner," no change to tuning-recommendation logic. See
# chord_vocabulary_analysis.py.

@dataclass
class ChordOccurrenceAnalysis:
    """
    One distinct chord+melody combination from a score's
    practical vocabulary (see
    chord_vocabulary_analysis.extract_chord_vocabulary()),
    analyzed against one specific tuning.

    occurrence_count: how many times this exact combination
        (same chord, same melody pitch class) appears in the
        score -- shown for transparency, not used to weight
        anything (see module notes on why repetition isn't
        weighted).
    example_measure: the first measure this combination
        occurs at, so a human can go look at it in the score.
    melody_note: display name (e.g. "B3") of the melody pitch
        class this combination pairs the chord with, or None
        if no melody note was found for any occurrence of this
        chord+position combination.
    usable_shape_count: how many playable shapes ChordService
        found for this chord in this tuning (verified +
        generated, after playability filtering) -- 0 means the
        chord itself has no usable voicing in this tuning at
        all, independent of melody.
    selected_shape: the shape select_shape_for_melody() (or,
        with no melody_note, the top of get_shapes()) would
        actually offer -- None only if usable_shape_count is 0.
    realization_tier: DIRECT_REALIZATION / INDIRECT_REALIZATION
        / NO_REALIZATION for selected_shape, or "" if there was
        no melody_note to evaluate against.
    voicing_quality_category: selected_shape's own
        ROOT_PRESENT / ROOTLESS_STRONG / ROOTLESS_WEAK (see
        music.classify_voicing_quality()), or "" if there's no
        selected_shape.
    """

    root: str

    quality_code: str

    quality_display: str | None

    chord_symbol: str

    melody_note: str | None

    occurrence_count: int

    example_measure: int

    usable_shape_count: int

    selected_shape: ChordShape | None

    realization_tier: str

    voicing_quality_category: str


@dataclass
class TuningChordAnalysis:
    """
    Aggregated ChordOccurrenceAnalysis results for one score
    analyzed against one tuning -- see
    chord_vocabulary_analysis.analyze_score_for_tuning().

    Counts are simple tallies over `occurrences` (one entry per
    distinct chord+melody combination, not per raw occurrence
    in the score -- see module notes), included for convenience
    since a human reading the report will want them, not as any
    kind of composite score. Comparing two TuningChordAnalysis
    results side by side is the actual evidence; nothing here
    declares one tuning better than another.
    """

    tuning_symbol: str

    occurrences: list[ChordOccurrenceAnalysis] = field(
        default_factory=list
    )

    direct_count: int = 0

    indirect_count: int = 0

    no_realization_count: int = 0

    no_melody_note_count: int = 0

    no_usable_shape_count: int = 0


# ---------------------------------------------------------
# Melody box analysis (hand-position measurement)
# ---------------------------------------------------------
#
# Diagnostic-only measurement of the melody passage between one
# chord occurrence and the next ("box"), and which strict
# four-fret hand positions can play through it without moving.
# See melody_box_analysis.py for the functions that produce
# these. No scoring, no "best" position or realization chosen
# here -- these are deliberately just measurements to inspect.

@dataclass
class NoteRealization:
    """
    One string/fret way to play a single melody note. fret=0
    means an open string.
    """

    string_index: int

    fret: int


@dataclass
class BoxMelodyNote:
    """
    One melody note within a box, with every playable
    realization (see fretboard.find_positions(), reused
    unchanged) and which hand positions those realizations
    make available.

    has_open_realization: True if ANY realization is an open
        string -- an open-string note is playable from every
        hand position and never forces a position change.
    fretted_positions: the set of hand positions (identified by
        index-finger fret) reachable via a FRETTED realization
        of this note specifically -- see
        melody_box_analysis.positions_covering_fret(). Does NOT
        include "every position," even when
        has_open_realization is True -- callers should check
        has_open_realization separately for that case.
    """

    midi: int

    measure: int

    beat: float

    realizations: list[NoteRealization] = field(
        default_factory=list
    )

    has_open_realization: bool = False

    fretted_positions: set[int] = field(default_factory=set)


@dataclass
class PositionRun:
    """
    How far one candidate starting hand position can continue
    through a box before it can no longer realize the next
    note, under the strict four-fret model.

    position: the index-finger fret identifying this hand
        position.
    notes_played: how many consecutive notes from the start of
        the box this position can play before failing (or the
        full box length if it never fails).
    breaks_at_note_index: index into the box's notes list where
        this position first fails, or None if it plays the
        whole box.
    breaking_realizations: the fretted realizations of the note
        that broke this position (empty if it never breaks) --
        shown for context, not because any one of them is
        preferred.
    destination_positions: every OTHER hand position that could
        play the breaking note (empty if it never breaks). This
        is a one-level-deep report -- it does not recursively
        track how far each destination position could continue
        from there.
    """

    position: int

    notes_played: int

    breaks_at_note_index: int | None = None

    breaking_realizations: list[NoteRealization] = field(
        default_factory=list
    )

    destination_positions: set[int] = field(default_factory=set)


@dataclass
class MelodyBox:
    """
    The melody passage from one chord occurrence through the
    note right before the next chord occurrence (or through the
    end of the score, for the final chord).

    chord: the Harmony this box starts at.
    next_chord: the Harmony that ends this box, or None if this
        is the score's last chord occurrence.
    notes: every melody note in the box, in order, each with
        its own realizations (see BoxMelodyNote).
    chord_shape: the chord shape associated with this box's
        starting chord, if one was supplied during analysis --
        None if no chord service was used, or none was
        available. Existing, unmodified ChordShape data; not a
        new hand-position model for the chord itself (see
        melody_box_analysis module notes on this limitation).
    position_runs: one PositionRun per candidate starting
        position -- every hand position capable of playing at
        least one note in this box via a fretted realization
        (the union of every note's fretted_positions). Empty if
        the box has no fretted notes at all (e.g. entirely open
        strings).
    """

    chord: Harmony

    next_chord: Harmony | None

    notes: list[BoxMelodyNote] = field(default_factory=list)

    chord_shape: ChordShape | None = None

    position_runs: list[PositionRun] = field(
        default_factory=list
    )


# ---------------------------------------------------------
# Chord-centered Playing Model
# ---------------------------------------------------------
#
# See playing_model.py and DESIGN.md. Structured results for
# evaluating melody locations in combination with playable
# chord shapes, rather than as two independent systems.

@dataclass
class ChordShapePlayability:
    """
    Intrinsic playability of one chord shape, independent of
    melody. See playing_model.analyze_chord_shape_playability().
    Higher score = more playable. Simple, documented heuristics
    -- not a physical hand model.
    """

    shape: str

    finger_count: int

    span: int

    geometry_penalty: float

    open_strings: list[int] = field(default_factory=list)

    score: float = 0.0


@dataclass
class MelodyChordCombination:
    """
    One melody note evaluated against one candidate chord
    shape -- the central unit of the Playing Model (section 5).
    """

    midi: int

    contained_in_chord: bool

    realization: NoteRealization | None

    free_finger: bool

    score: float = 0.0


@dataclass
class PhraseSolution:
    """
    One chord-centered phrase: a candidate chord shape and how
    well it, together with its playability, serves the melody
    immediately before (lead-in) and after (box) its own chord
    occurrence -- section 6.
    """

    chord: Harmony

    chord_shape: ChordShape | None

    shape_playability: ChordShapePlayability | None

    lead_in: list[MelodyChordCombination] = field(
        default_factory=list
    )

    box_notes: list[MelodyChordCombination] = field(
        default_factory=list
    )

    fifth_string_bonus: float = 0.0

    score: float = 0.0


@dataclass
class TuningPlayingModelResult:
    """
    Aggregated Playing Model result for one score analyzed
    against one tuning -- section 12. A diagnostic score,
    comparable across tunings, but not (yet) blended into
    optimizer.py's own tuning score -- see playing_model.py's
    module docstring for why.
    """

    tuning_symbol: str

    phrases: list[PhraseSolution] = field(default_factory=list)

    continuity_bonus: float = 0.0

    total_score: float = 0.0


# ---------------------------------------------------------
# BO-51 -- chord/melody realization diagnostics
# ---------------------------------------------------------
#
# Read-only, diagnostic-only additions (see playing_model.
# diagnose_melody_chord_realization()). Do not confuse
# MelodyChordCombination.contained_in_chord (above) with the
# CHORD_TONE_* classifications here -- contained_in_chord
# checks the ACTUAL SOUNDING VOICING's own pitch classes (via
# fretboard.sounding_notes()), never chord theory, and is left
# completely unchanged by BO-51. The classifications below are
# new: they additionally check chord-theory membership (music.
# chord_tones()) so a pitch absent from theory (NON_CHORD_TONE)
# can be told apart from a pitch theory says belongs but this
# specific voicing doesn't sound (CHORD_TONE_NOT_IN_VOICING) --
# a distinction the existing boolean alone cannot make.

NON_CHORD_TONE = "non_chord_tone"

CHORD_TONE_NOT_IN_VOICING = "chord_tone_not_in_voicing"

CHORD_TONE_IN_VOICING = "chord_tone_in_voicing"

PLAYABLE_FROM_CHORD_POSITION = "playable_from_chord_position"

AVAILABLE_BUT_POSITION_CHANGE_REQUIRED = (
    "available_but_position_change_required"
)


@dataclass
class ChordMelodyRealization:
    """
    BO-51 -- the full relationship between ONE melody note and
    ONE chord voicing, for diagnostic inspection. Built from
    already-computed Playing Model data (playing_model.
    evaluate_combination() and melody_box_analysis.realize_note(),
    both reused unmodified) -- not a second, independent
    fretboard-position algorithm. See playing_model.
    diagnose_melody_chord_realization()'s own docstring for how
    each field is derived.

    classification is one of the constants immediately above
    this class -- always exactly one of the five, in the same
    priority order the docstring for diagnose_melody_chord_
    realization() documents (a note that's NON_CHORD_TONE is
    never also reported as CHORD_TONE_NOT_IN_VOICING, etc.).
    """

    chord_symbol: str

    melody_pitch: int

    melody_pitch_class: int

    melody_octave: int

    chord_contains_pitch: bool

    voicing_contains_pitch: bool

    # Every playable string/fret realization of this melody
    # pitch in this tuning (fretboard.find_positions(), via
    # melody_box_analysis.realize_note(), reused unchanged --
    # not recomputed here). Never empty-vs-populated inconsistently
    # with best_realization: best_realization is None only when
    # this list is empty too.
    candidate_realizations: list[NoteRealization] = field(
        default_factory=list
    )

    # The SAME best-scoring realization playing_model.
    # evaluate_combination() already selects -- reused directly,
    # not recomputed by different logic.
    best_realization: NoteRealization | None = None

    working_fret: int | None = None

    fret_distance: int | None = None

    free_finger_available: bool = False

    # Independent of chord_contains_pitch/voicing_contains_pitch
    # -- whether THIS pitch's own best_realization is reachable
    # without abandoning the chord's own hand position (open
    # string, or within its own working-fret window), regardless
    # of whether the pitch is a chord tone at all. See
    # diagnose_melody_chord_realization()'s own docstring for
    # why this is a separate dimension from classification below,
    # not folded into it.
    playable_from_chord_position: bool = False

    classification: str = NON_CHORD_TONE