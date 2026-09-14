"""
tests/test_bo171_output_key_transposition.py

Focused tests for BO-171: transposing a parsed score's melody/
harmony data to a specific output key, before tuning analysis
and generation -- while "Keep input key" (output_key=None)
remains the default and reproduces prior behavior exactly.

Does NOT test "Best key" -- that is a separate, not-yet-
designed feature (BO-171's own investigation, Part 4) and is
out of scope here.
"""

import sys

sys.path.insert(0, '.')

import copy

import zipfile

import xml.etree.ElementTree as ET

from parser import MuseScoreFile

from transposition import semitones_for_output_key, transpose_score

from music import chord_display_symbol, pitch_name

from tunings import get_tunings

from chord_library import ChordLibrary

from chord_service import ChordService

from score_generator import generate_tab_from_template

import main

from conftest import fixture_path, TEST_OUTPUT_DIR


def _load_aureolin():

    p = MuseScoreFile(str(fixture_path('Aureolin.mscz')))

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.estimate_key()

    p.read_harmonies(staff_used)

    return p, staff_used


# ---------------------------------------------------------
# 1 -- melody MIDI pitches transpose correctly
# ---------------------------------------------------------

def test_melody_midi_pitches_transpose_correctly():

    score, staff_used = _load_aureolin()

    assert score.key == 'B minor'

    original_midi_values = [
        note['midi'] for note in score.notes
    ]

    original_score_notes_midi = [
        note.midi for note in score.score.notes
    ]

    semitones = semitones_for_output_key(score.key, 'C')

    assert semitones == 1

    transpose_score(score, semitones)

    for original, note in zip(original_midi_values, score.notes):

        assert note['midi'] == original + 1

    for original, note in zip(
        original_score_notes_midi, score.score.notes
    ):

        assert note.midi == original + 1


# ---------------------------------------------------------
# 2 -- harmony roots transpose correctly
# ---------------------------------------------------------

def test_harmony_roots_transpose_correctly():

    score, staff_used = _load_aureolin()

    original_root_pcs = [h.root_pc for h in score.harmonies]

    semitones = semitones_for_output_key(score.key, 'C')

    transpose_score(score, semitones)

    for original, harmony in zip(
        original_root_pcs, score.harmonies
    ):

        assert harmony.root_pc == (original + semitones) % 12


def test_harmony_root_wraps_correctly_across_the_octave():

    # A direct, deliberately wrap-forcing case: B (pc 11) + 2
    # semitones must land on C# (pc 1), not 13.
    score, staff_used = _load_aureolin()

    b_harmony = next(
        h for h in score.harmonies if h.root_pc == 11
    )

    transpose_score(score, 2)

    assert b_harmony.root_pc == 1


# ---------------------------------------------------------
# 3 -- harmony tones transpose correctly
# ---------------------------------------------------------

def test_harmony_tones_transpose_correctly():

    score, staff_used = _load_aureolin()

    original_tones_by_harmony = [
        list(h.tones) for h in score.harmonies
    ]

    semitones = semitones_for_output_key(score.key, 'C')

    transpose_score(score, semitones)

    for original_tones, harmony in zip(
        original_tones_by_harmony, score.harmonies
    ):

        expected = [
            (tone + semitones) % 12 for tone in original_tones
        ]

        assert harmony.tones == expected


# ---------------------------------------------------------
# 4 -- quality_code unchanged, symbol regenerated correctly
# ---------------------------------------------------------

def test_quality_code_unchanged_and_symbol_regenerated():

    score, staff_used = _load_aureolin()

    original_quality_codes = [
        h.quality_code for h in score.harmonies
    ]

    semitones = semitones_for_output_key(score.key, 'C')

    transpose_score(score, semitones)

    for original_quality, harmony in zip(
        original_quality_codes, score.harmonies
    ):

        assert harmony.quality_code == original_quality

        expected_symbol = chord_display_symbol(
            pitch_name(harmony.root_pc), harmony.quality_code
        )

        assert harmony.symbol == expected_symbol


def test_specific_real_chord_symbol_regenerated_correctly():

    # A concrete, real example rather than only a structural
    # check: the real Aureolin score's own opening Bm chord
    # (confirmed directly) must become Cm, not a mistransposed
    # or stale symbol, when transposed up one semitone to C.
    score, staff_used = _load_aureolin()

    bm_harmony = next(
        h for h in score.harmonies if h.symbol == 'Bm'
    )

    transpose_score(score, 1)

    assert bm_harmony.symbol == 'Cm'

    assert bm_harmony.quality_code == 'm'


# ---------------------------------------------------------
# 5 -- the optimizer receives/uses the transposed key
# ---------------------------------------------------------

def test_optimizer_receives_transposed_key_end_to_end():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gDGBD',
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='C'
    )

    score_result = result['scores'][0]

    assert score_result['key'] == 'C minor'


def test_tuning_analyzer_uses_transposed_key_for_key_bonus():

    from optimizer import TuningAnalyzer

    score, staff_used = _load_aureolin()

    semitones = semitones_for_output_key(score.key, 'C')

    new_key = transpose_score(score, semitones)

    score.key = new_key

    analyzer = TuningAnalyzer(
        score.notes, score.key, score.harmonies, score.score.notes
    )

    assert analyzer.key == 'C minor'


# ---------------------------------------------------------
# 6 -- generated <KeySig> reflects the requested output key
# (confirmed directly, BO-171's own investigation: the actual
# production TAB-only path always writes concertKey "0"
# regardless of source OR transposed key -- a TAB staff shows
# no accidentals/key signature visually at all, so this is
# already correct, existing behavior; this test locks that
# down as a regression guard specifically for the transposed
# case, not merely the untransposed one).
# ---------------------------------------------------------

def test_generated_keysig_is_unaffected_by_output_key():

    score, staff_used = _load_aureolin()

    semitones = semitones_for_output_key(score.key, 'C')

    new_key = transpose_score(score, semitones)

    score.key = new_key

    score.score.key = new_key

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            score, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            str(TEST_OUTPUT_DIR), service,
            filename='bo171_keysig_test.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    root = ET.fromstring(content)

    keysig_found = False

    for element in root.iter():

        if element.tag.split('}')[-1] != 'KeySig':

            continue

        keysig_found = True

        concert_key = element.find('{*}concertKey')

        assert concert_key.text == '0', (
            f"Expected the TAB staff's own concertKey to remain "
            f"'0' (its existing, unaffected behavior), got "
            f"{concert_key.text!r}."
        )

    assert keysig_found, "Expected at least one KeySig element."


# ---------------------------------------------------------
# 7 -- "Keep input key" preserves existing behavior exactly
# ---------------------------------------------------------

def test_keep_input_key_produces_identical_result_to_omitting_it():

    result_explicit_none = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gDGBD',
        output_folder=str(TEST_OUTPUT_DIR),
        output_key=None
    )

    result_omitted = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gDGBD',
        output_folder=str(TEST_OUTPUT_DIR)
    )

    key_explicit = result_explicit_none['scores'][0]['key']

    key_omitted = result_omitted['scores'][0]['key']

    assert key_explicit == key_omitted == 'B minor'


def test_keep_input_key_does_not_mutate_notes_or_harmonies():

    score, staff_used = _load_aureolin()

    original_midi_values = [
        note['midi'] for note in score.notes
    ]

    original_root_pcs = [h.root_pc for h in score.harmonies]

    original_symbols = [h.symbol for h in score.harmonies]

    # semitones=0 is transpose_score()'s own explicit no-op path
    # -- the exact case output_key=None ultimately reaches when
    # the requested key already equals the source key, and the
    # same mechanism "Keep input key" itself relies on never
    # being invoked at all (main.py never calls transpose_score()
    # when output_key is None).
    transpose_score(score, 0)

    assert [n['midi'] for n in score.notes] == original_midi_values

    assert [
        h.root_pc for h in score.harmonies
    ] == original_root_pcs

    assert [
        h.symbol for h in score.harmonies
    ] == original_symbols


# ---------------------------------------------------------
# 8 -- a real representative score transposes without losing
# melody/harmony consistency
# ---------------------------------------------------------

def test_real_score_transposition_preserves_note_and_harmony_counts():

    original_score, original_staff_used = _load_aureolin()

    original_note_count = len(original_score.notes)

    original_harmony_count = len(original_score.harmonies)

    original_pitch_classes = [
        note['midi'] % 12 for note in original_score.notes
    ]

    transposed_score, staff_used = _load_aureolin()

    semitones = semitones_for_output_key(
        transposed_score.key, 'F#'
    )

    transpose_score(transposed_score, semitones)

    # Nothing is added or dropped by transposition -- same
    # counts, same order, only shifted pitch.
    assert len(transposed_score.notes) == original_note_count

    assert (
        len(transposed_score.harmonies) == original_harmony_count
    )

    transposed_pitch_classes = [
        note['midi'] % 12 for note in transposed_score.notes
    ]

    for original_pc, transposed_pc in zip(
        original_pitch_classes, transposed_pitch_classes
    ):

        assert transposed_pc == (original_pc + semitones) % 12


def test_real_score_end_to_end_generation_after_transposition():

    # The full, real pipeline: parse, transpose, generate -- and
    # confirm the run genuinely completes and produces a real
    # TAB file, with melody/harmony data that stayed mutually
    # consistent all the way through generation (a chord-shape
    # exception count that's a plausible integer, not a crash
    # or an empty/broken result).
    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gDGBD',
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='D'
    )

    score_result = result['scores'][0]

    assert score_result['key'].startswith('D ')

    generated = score_result['generated_files'][0]

    assert generated['error'] is None

    assert generated['tab_path'] is not None

    assert generated['tab_path'].exists()
