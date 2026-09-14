"""
transposition.py

BO-171 -- a small, self-contained helper for transposing a
parsed score (melody notes + harmony chords) to a different
output key, preserving the original mode (major/minor). Used
by main.run_optimizer() when a specific output key is
explicitly requested (not "Keep input key").

Does NOT implement Best key -- that requires a separate,
yet-to-be-designed scoring architecture (BO-171's own
investigation, Part 4) and is explicitly out of scope here.
"""

from music import pitch_name, chord_display_symbol


# Every root note name parser.estimate_key() can produce
# (source-key side), plus every one of main.PITCH_CLASS_TO_
# NOTE_NAME's own 12 sharp-spelled entries (target-key side --
# confirmed, BO-172's own testing, this dict must recognize
# every value the GUI's output-key dropdown can actually select,
# not only estimate_key()'s own flat-preferring spellings, or
# semitones_for_output_key() genuinely raises/KeyErrors for a
# real, selectable GUI option like "D#"). Mapped to each one's
# own pitch class (0-11).
ROOT_NAME_TO_PITCH_CLASS = {
    "CB": 11, "GB": 6, "DB": 1, "AB": 8, "EB": 3, "BB": 10,
    "F": 5, "C": 0, "G": 7, "D": 2, "A": 9, "E": 4, "B": 11,
    "F#": 6, "C#": 1,
    "D#": 3, "G#": 8, "A#": 10,
}


def semitones_for_output_key(source_key, target_note_name):
    """
    The signed semitone shift required to move source_key's own
    root (e.g. "F" from "F major") to target_note_name (e.g.
    "C"), preserving whichever mode source_key already has --
    transposition never changes major to minor or vice versa.

    source_key: the parsed score's own `key` string (e.g.
        "F major", "B minor" -- parser.estimate_key()'s own
        output format).
    target_note_name: one of main.PITCH_CLASS_TO_NOTE_NAME
        (e.g. "C", "F#") -- the GUI's own output-key selection.

    Returns the smallest-magnitude signed shift (-5..+6) that
    reaches the target pitch class -- e.g. F->C is -5 (not
    +7), since that's genuinely the closer direction and keeps
    generated pitches in a more natural register rather than
    forcing every transposition upward regardless of distance.

    Raises ValueError if source_key's own root can't be parsed
    (should never happen for a key string estimate_key() itself
    produced -- flagged loudly rather than silently doing
    nothing if it somehow does).
    """

    root_name = source_key.split()[0].upper()

    if root_name not in ROOT_NAME_TO_PITCH_CLASS:

        raise ValueError(
            f"Can't determine the root pitch class of source "
            f"key {source_key!r} -- unrecognized root "
            f"{root_name!r}."
        )

    source_pc = ROOT_NAME_TO_PITCH_CLASS[root_name]

    target_pc = ROOT_NAME_TO_PITCH_CLASS[
        target_note_name.upper()
    ]

    raw_shift = (target_pc - source_pc) % 12

    if raw_shift > 6:

        return raw_shift - 12

    return raw_shift


def transpose_score(score, semitones):
    """
    Transposes every melody note and harmony in `score` (a
    parser.MuseScoreFile instance -- its own `.notes` (dict
    format, "old format kept for optimizer compatibility" per
    parser.py's own comment) and `.score.notes` (models.Note
    format), plus `.harmonies`/`.score.harmonies`, which are
    the SAME shared Harmony instances -- confirmed directly,
    parser.read_harmonies() appends one Harmony object to both
    lists, so a single pass here transposes both) by
    `semitones`, in place.

    Harmony.quality_code is never changed -- quality is
    transposition-invariant. Harmony.symbol is regenerated via
    the existing music.chord_display_symbol() rather than
    attempting to transpose the symbol string itself.

    Returns the new key string (same mode, new root), for the
    caller to assign to score.key/score.score.key.

    semitones=0 (source key already equals the requested output
    key) is a no-op: returns score.key unchanged, and does not
    touch notes/harmonies at all.
    """

    if semitones == 0:

        return score.key

    for note in score.notes:

        note["midi"] += semitones

    for note in score.score.notes:

        note.midi += semitones

    for harmony in score.harmonies:

        harmony.root_pc = (harmony.root_pc + semitones) % 12

        harmony.tones = [
            (tone + semitones) % 12 for tone in harmony.tones
        ]

        harmony.symbol = chord_display_symbol(
            pitch_name(harmony.root_pc), harmony.quality_code
        )

    source_root_name = (
        score.key.split()[0].upper() if score.key else "C"
    )

    source_mode = (
        score.key.split()[-1] if score.key else "major"
    )

    source_pc = ROOT_NAME_TO_PITCH_CLASS.get(
        source_root_name, 0
    )

    new_root_pc = (source_pc + semitones) % 12

    new_root_name = pitch_name(new_root_pc)

    return f"{new_root_name} {source_mode}"
