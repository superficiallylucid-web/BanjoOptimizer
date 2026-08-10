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
    """

    measure: int

    root_pc: int

    quality_code: str

    symbol: str

    tones: list[int] = field(default_factory=list)


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
        with a chord occurrence, using the finest position
        granularity the parser currently provides: which
        measure the chord falls in (Harmony has no beat/tick
        position -- see read_harmonies() in parser.py). Returns
        the first note (by parse order, which matches time
        order within a voice) in that same measure, or None if
        there isn't one.

        This is a measure-level approximation, not a true
        beat-accurate match. If a measure contains more than
        one melody note, this doesn't attempt to pick "the"
        correct one for this specific chord occurrence -- it's
        the first note in the measure, full stop. Refining this
        needs beat-level position tracking, which isn't part of
        the parser yet.
        """

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
    confidence: placeholder for a future score-margin-based
        confidence value (e.g. for grouping near-tied
        recommendations). Not yet computed -- None until that
        logic exists.
    """

    name: str

    symbol: str

    category: str = ""

    score: float = 0.0

    advantages: list[str] = field(default_factory=list)

    tradeoffs: list[str] = field(default_factory=list)

    shared_features: list[str] = field(default_factory=list)

    confidence: float | None = None


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