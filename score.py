"""
score.py

Data classes used throughout Banjo Optimizer.

These classes contain musical information only.
They know nothing about MuseScore, XML, or banjo tuning.
"""

from dataclasses import dataclass, field


@dataclass
class Harmony:
    measure: int
    beat: float
    name: str


@dataclass
class Lyric:
    measure: int
    beat: float
    text: str


@dataclass
class Note:
    measure: int
    beat: float
    midi: int
    duration: int

    voice: int = 1
    string: int | None = None
    fret: int | None = None

    harmony: Harmony | None = None
    lyric: Lyric | None = None


@dataclass
class Score:
    title: str = ""
    composer: str = ""
    key: str = ""
    time_signature: str = ""

    notes: list[Note] = field(default_factory=list)
    harmonies: list[Harmony] = field(default_factory=list)
    lyrics: list[Lyric] = field(default_factory=list)