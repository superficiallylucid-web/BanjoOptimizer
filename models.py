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
    """

    tuning: str

    root: str

    quality: str

    shape: str

    comfort_code: int | None = None

    comfort_explanation: str = ""

    comments: str = ""

    verified: bool | None = None