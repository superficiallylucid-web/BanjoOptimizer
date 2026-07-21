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

    def add_note(self, note: Note):
        self.notes.append(note)

    def add_measure(self, measure: Measure):
        self.measures.append(measure)

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
    name: str

    symbol: str

    score: float

    reasons: list[str] = field(default_factory=list)