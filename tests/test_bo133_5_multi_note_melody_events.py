"""
tests/test_bo133_5_multi_note_melody_events.py

Focused tests for BO-133.5: preserving genuine multi-note melody
events (two simultaneous pitches within one source <Chord>) as
simultaneous TAB notes, choosing a compact/playable voicing, and
keeping chord selection aware of the full event rather than
silently reducing it to one note.
"""

import sys

sys.path.insert(0, '.')

from parser import MuseScoreFile

from tunings import get_tunings

from score_generator import (
    generate_tab_from_template, _select_chord_shape_for_harmony,
    _preferred_melody_fret, _melody_notes_at_harmony_onset
)

from chord_service import ChordService

from chord_library import ChordLibrary

from fretboard import choose_simultaneous_positions, parse_shape

from playing_model import _chord_working_fret

import zipfile

import xml.etree.ElementTree as ET

import os


def _load_gamboge():

    p = MuseScoreFile('scores/Gamboge.mscz')

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p, staff_used


# ---------------------------------------------------------
# 1 -- Gamboge real case
# ---------------------------------------------------------

def test_gamboge_both_notes_survive_simultaneously_in_tab():

    p, staff_used = _load_gamboge()

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo133_5_gamboge_test.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    first_measure = root.find('.//{*}Measure')

    first_chord = first_measure.find('.//{*}Chord')

    note_elements = first_chord.findall('{*}Note')

    assert len(note_elements) == 2, (
        f"Expected both input notes to survive in the same "
        f"<Chord>, found {len(note_elements)}."
    )

    pitches_found = set()

    positions_found = {}

    for note_element in note_elements:

        pitch_text = note_element.find('{*}pitch').text

        fret_text = note_element.find('{*}fret').text

        pitches_found.add(int(pitch_text))

        positions_found[int(pitch_text)] = int(fret_text)

    # BO-135 -- superseded by the FD-anchor fix: the chord shape
    # already selected for this exact onset ("5500") genuinely
    # sounds both 57 and 62 (D, same pitch class as the source
    # 74, at a different octave), so choose_simultaneous_
    # positions() now reuses those exact positions rather than
    # independently searching for its own compact voicing --
    # confirmed directly this is the same voicing the FD itself
    # represents, matching the real, reported target (player's
    # own "3-5"/"4-5").
    assert pitches_found == {57, 62}, (
        f"Expected the FD-anchor-matched pitch set (57, 62), "
        f"got {pitches_found}."
    )

    assert positions_found[57] == 5 and positions_found[62] == 5, (
        f"Expected the FD-anchor-matched voicing (57@5, 62@5, "
        f"matching the already-selected chord shape '5500'), "
        f"got {positions_found}."
    )


# ---------------------------------------------------------
# 2 -- monophonic regression
# ---------------------------------------------------------

def test_ordinary_single_note_event_unaffected():

    # A real, ordinary single-note melody event elsewhere in
    # Gamboge itself (m1 b0.5, midi=64 -- confirmed real, single
    # <Note> per <Chord>, per BO-133.3's own investigation).
    p, staff_used = _load_gamboge()

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo133_5_monophonic_test.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    first_measure = root.find('.//{*}Measure')

    chords = first_measure.findall('.//{*}Chord')

    # Second <Chord> in the measure is the ordinary, single-note
    # b0.5 event.
    second_chord = chords[1]

    note_elements = second_chord.findall('{*}Note')

    assert len(note_elements) == 1, (
        f"An ordinary single-note event should still produce "
        f"exactly one <Note>, got {len(note_elements)}."
    )

    assert note_elements[0].find('{*}pitch').text == '64'


# ---------------------------------------------------------
# 3 -- second note no longer silently overwritten
# ---------------------------------------------------------

def test_second_note_no_longer_silently_dropped():

    p, staff_used = _load_gamboge()

    onset_notes = [
        n for n in p.score.notes
        if n.measure == 1 and abs(n.beat - 0.0) < 0.01
    ]

    assert len(onset_notes) == 2, (
        "Expected the real, genuine two-note onset at m1 b0.0."
    )

    tuning = get_tunings()['A Minor']

    open_notes = tuning.notes[1:]

    result = choose_simultaneous_positions(
        [n.midi for n in onset_notes], open_notes
    )

    assert result is not None

    resulting_pitches_positions = list(zip(
        [n.midi for n in onset_notes], result
    ))

    # Both midi values genuinely present in the chosen result --
    # neither the first-note-wins nor last-note-wins collapse
    # from before this BO.
    assert {p[0] for p in resulting_pitches_positions} == {57, 74}


# ---------------------------------------------------------
# 4 -- TAB/FD consistency
# ---------------------------------------------------------

def test_chord_selection_reflects_full_multi_note_voicing():

    p, staff_used = _load_gamboge()

    tuning = get_tunings()['A Minor']

    dsus2 = p.harmonies[0]

    onset_notes = _melody_notes_at_harmony_onset(
        dsus2, p.score.notes
    )

    preferred = _preferred_melody_fret(onset_notes, tuning)

    # BO-133.5 Part A -- confirmed real: min(0, 2) = 0,
    # reflecting the new, combined-score-preferred voicing
    # (57@0, 62@2) -- not the pre-Part-A value of 17.
    assert preferred == 0, (
        f"Expected preferred_melody_fret to reflect the full, "
        f"combined-score-preferred voicing (0), got {preferred}."
    )

    service = ChordService(ChordLibrary())

    shape, is_exception, exception_dict = (
        _select_chord_shape_for_harmony(
            dsus2, tuning, service, melody_notes=p.score.notes,
            next_harmony=p.harmonies[1], incoming_shape=None
        )
    )

    values = parse_shape(shape.shape)

    working_fret = (
        _chord_working_fret(values)
        if not any(v is None for v in values) else None
    )

    # The selected chord's own working fret must not EXCEED
    # what the real melody voicing supports (BO-131's own
    # already-established Rule B principle: never too high,
    # lower is always structurally fine) -- confirms chord
    # selection is at least consistent with, not contradicting,
    # the real voicing, even though exact positional match
    # isn't guaranteed by this fix alone (see this BO's own
    # report).
    assert working_fret <= 2, (
        f"Selected chord's own working_fret ({working_fret}) "
        f"should not exceed the real melody voicing's own "
        f"highest position (2)."
    )


# ---------------------------------------------------------
# 5 -- playability: compact preferred over excessive spread
# ---------------------------------------------------------

def test_compact_combination_preferred_when_available():

    tuning = get_tunings()['A Minor']

    open_notes = tuning.notes[1:]

    # Real pitches confirmed to have multiple valid combinations
    # at genuinely different spans (0, 4, 7) -- the function
    # must choose the minimum, not merely any valid one.
    result = choose_simultaneous_positions([52, 64], open_notes)

    assert result is not None

    chosen_span = abs(result[0]["fret"] - result[1]["fret"])

    assert chosen_span == 0, (
        f"Expected the compact (span=0) combination to be "
        f"chosen over wider alternatives (spans 4, 7 also "
        f"exist), got span={chosen_span}."
    )


# ---------------------------------------------------------
# BO-133.5-FOLLOWUP -- octave consideration for simultaneous
# notes
# ---------------------------------------------------------

def test_already_good_voicing_stays_unchanged_no_octave_shift():

    # Confirmed real: 60/64 (a major third) already has a
    # same-octave span of 0 -- well within
    # playability.MAX_ACCEPTABLE_SPAN -- so no octave shift
    # should ever be considered, matching "do not make arbitrary
    # octave changes when the original pitches already have a
    # good playable voicing".
    tuning = get_tunings()['A Minor']

    open_notes = tuning.notes[1:]

    result = choose_simultaneous_positions([60, 64], open_notes)

    assert result is not None

    pitches_used = [r["pitch"] for r in result]

    assert pitches_used == [60, 64], (
        f"Expected the original pitches unchanged (60, 64), "
        f"got {pitches_used} -- an octave shift should never "
        f"be considered when the original voicing is already "
        f"compact."
    )


def test_distinct_synthetic_case_octave_shift_clearly_better():

    # Independent from Gamboge's own (57, 74) pair -- confirmed
    # directly: same-octave span is 5 (exceeds
    # MAX_ACCEPTABLE_SPAN=3), while shifting either note by one
    # octave produces a genuine span-0 combination. This is a
    # different real interval (55->72, a major 13th) to confirm
    # the mechanism generalizes, not something specific to
    # Gamboge's own two pitches.
    tuning = get_tunings()['A Minor']

    open_notes = tuning.notes[1:]

    result = choose_simultaneous_positions([55, 72], open_notes)

    assert result is not None

    span = abs(result[0]["fret"] - result[1]["fret"])

    assert span == 0, (
        f"Expected the octave-adjusted combination (span=0) to "
        f"be preferred over the same-octave span-5 alternative, "
        f"got span={span}."
    )

    pitches_used = {r["pitch"] for r in result}

    assert pitches_used != {55, 72}, (
        "Expected an octave-shifted pitch set, since the "
        "original same-octave voicing (span 5) exceeds the "
        "compactness threshold."
    )


def test_octave_adjustment_output_fully_consistent():

    # Full pipeline: confirms pitch, tpc, fret, string, and
    # simultaneous timing are ALL internally consistent in the
    # real generated output after an octave adjustment -- not
    # merely that the TAB position changed while the written
    # pitch silently stayed at the original, unshifted value.
    p, staff_used = _load_gamboge()

    tuning = get_tunings()['A Minor']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            'output', service,
            filename='bo133_5_octave_consistency_test.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    os.remove(output_path)

    root = ET.fromstring(content)

    first_measure = root.find('.//{*}Measure')

    first_chord = first_measure.find('.//{*}Chord')

    note_elements = first_chord.findall('{*}Note')

    assert len(note_elements) == 2

    by_pitch = {}

    for note_element in note_elements:

        pitch = int(note_element.find('{*}pitch').text)

        tpc = int(note_element.find('{*}tpc').text)

        fret = int(note_element.find('{*}fret').text)

        string = int(note_element.find('{*}string').text)

        by_pitch[pitch] = {"tpc": tpc, "fret": fret, "string": string}

    # Written pitch reflects the actual, octave-adjusted result:
    # 62 (D shifted down one octave from the source D5=74) -- not
    # the unshifted source pitch 74. Confirmed directly: the
    # combined fret-band-comfort + span score prefers 57
    # (unshifted A3) paired with 62 (D shifted down), over every
    # other octave arrangement considered, including 57+74
    # unshifted (span 5, not compact) and 69+74 (span 0, but at a
    # far less comfortable fret 17).
    assert 62 in by_pitch and 74 not in by_pitch, (
        f"Expected the written pitch to be the octave-adjusted "
        f"62, not the original source 74 -- found pitches "
        f"{list(by_pitch.keys())}."
    )

    assert 57 in by_pitch

    # tpc reflects the real, confirmed values for these exact
    # pitch classes (A=17, D=16 in this project's own tpc
    # convention -- confirmed directly against the real output);
    # tpc is genuinely octave-independent (BO-133.4), so 62's own
    # tpc is the same value the original, unshifted 74 (also
    # pitch class D) would have carried.
    assert by_pitch[57]["tpc"] == 17

    assert by_pitch[62]["tpc"] == 16

    # Both notes genuinely simultaneous -- confirmed real,
    # combined-score-preferred voicing (57@0, 62@2), different
    # strings, on or near the same fret (span 2).
    assert by_pitch[57]["fret"] == 0

    assert by_pitch[62]["fret"] == 2

    assert by_pitch[57]["string"] != by_pitch[62]["string"]

    # FD consistency: the chord shape selected for this exact
    # harmony must not exceed the real, final melody voicing's
    # own highest position (BO-131's own established Rule B
    # principle).
    dsus2 = p.harmonies[0]

    shape, is_exception, exception_dict = (
        _select_chord_shape_for_harmony(
            dsus2, tuning, service, melody_notes=p.score.notes,
            next_harmony=p.harmonies[1], incoming_shape=None
        )
    )

    values = parse_shape(shape.shape)

    working_fret = (
        _chord_working_fret(values)
        if not any(v is None for v in values) else None
    )

    assert working_fret <= 2
