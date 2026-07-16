"""
models.py

Core data models for Banjo Optimizer.

Contains:
- Note
- Measure
- Score
- Tuning
- TuningResult
"""

from dataclasses import dataclass, field


@dataclass
class Tuning:
    name: str
    symbol: str
    notes: list[int]

    category: str
    popularity: int

    key_strengths: dict = field(default_factory=dict)

    # New informational fields
    base_tuning: str | None = None
    capo: int = 0
    fifth_string_note: str | None = None

# ---------------------------------------------------------
# Note model
# ---------------------------------------------------------

@dataclass
class Note:
    """
    Represents one musical note.
    """

    midi: int

    measure: int = 0

    beat: float = 0

    duration: float = 0

    voice: int = 0


    @property
    def name(self):

        return midi_to_note_name(
            self.midi
        )


    @property
    def pitch_class(self):

        return pitch_class(
            self.midi
        )


    def __str__(self):

        return self.name



# ---------------------------------------------------------
# Measure model
# ---------------------------------------------------------

@dataclass
class Measure:
    """
    Represents one measure.
    """

    number: int

    notes: list[Note] = field(
        default_factory=list
    )


    def add_note(self, note):

        self.notes.append(
            note
        )



# ---------------------------------------------------------
# Score model
# ---------------------------------------------------------

@dataclass
class Score:
    """
    Represents a complete musical score.
    """

    title: str = "Unknown Title"

    composer: str = ""

    key: str = "Unknown"

    key_confidence: float = 0

    time_signature: str = "Unknown"


    notes: list[Note] = field(
        default_factory=list
    )


    measures: list[Measure] = field(
        default_factory=list
    )


    def add_note(self, note):

        self.notes.append(
            note
        )


    def add_measure(self, measure):

        self.measures.append(
            measure
        )


    @property
    def note_count(self):

        return len(
            self.notes
        )


    @property
    def lowest_note(self):

        if not self.notes:

            return None


        return min(
            self.notes,
            key=lambda n: n.midi
        )


    @property
    def highest_note(self):

        if not self.notes:

            return None


        return max(
            self.notes,
            key=lambda n: n.midi
        )


    @property
    def range_description(self):

        low = self.lowest_note
        high = self.highest_note


        if not low or not high:

            return "Unknown"


        return (
            f"{low.name} - {high.name}"
        )



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
    key_strengths: dict

    # Practical setup information
    base_tuning: str = ""
    capo: int = 0
    fifth_string_note: str = ""


# ---------------------------------------------------------
# Tuning analysis result
# ---------------------------------------------------------

@dataclass
class TuningResult:
    """
    Stores optimizer output.
    """

    name: str

    symbol: str

    score: float

    reasons: list[str] = field(
        default_factory=list
    )