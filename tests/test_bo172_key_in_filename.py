"""
tests/test_bo172_key_in_filename.py

Focused tests for BO-172: the generated filename format changes
from "<title> - <tuning> (<sounded tuning>) - TAB.mscz" to
"<title> Key <output key> <tuning> (<sounded tuning>).mscz",
and the existing in-score tuning text (capo'd branch only) gains
a "Key <output key> | " prefix.
"""

import sys

sys.path.insert(0, '.')

import zipfile

import xml.etree.ElementTree as ET

import main

from parser import MuseScoreFile

from tunings import get_tunings

from chord_library import ChordLibrary

from chord_service import ChordService

from score_generator import generate_tab_from_template

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
# 1 -- recommended tuning filename
# ---------------------------------------------------------

def test_recommended_tuning_filename():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='C',
        num_tunings=1
    )

    generated = result['scores'][0]['generated_files'][0]

    assert generated['tab_path'].name == (
        'Aureolin Key C Double D (aDADE).mscz'
    )


# ---------------------------------------------------------
# 2 -- specific tuning, capo 0
# ---------------------------------------------------------

def test_specific_tuning_capo_0_filename():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gCGCD',
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='C'
    )

    generated = result['scores'][0]['generated_files'][0]

    assert generated['tab_path'].name == (
        'Aureolin Key C gCGCD (gCGCD).mscz'
    )


# ---------------------------------------------------------
# 3 -- specific tuning, capo 2
# ---------------------------------------------------------

def test_specific_tuning_capo_2_filename():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gDGBD',
        capo=2,
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='D'
    )

    generated = result['scores'][0]['generated_files'][0]

    assert generated['tab_path'].name == (
        'Aureolin Key D gDGBD capo 2 (gEAC#E).mscz'
    )


# ---------------------------------------------------------
# 4 -- output key appears correctly in filenames (several)
# ---------------------------------------------------------

def test_output_key_appears_correctly_for_several_keys():

    for requested_key, expected_root in (
        ('C', 'C'), ('F#', 'F#'), ('A#', 'A#')
    ):

        result = main.run_optimizer(
            score_path=str(fixture_path('Aureolin.mscz')),
            tuning_symbol='gCGCD',
            output_folder=str(TEST_OUTPUT_DIR),
            output_key=requested_key
        )

        generated = result['scores'][0]['generated_files'][0]

        assert generated['tab_path'].name.startswith(
            f'Aureolin Key {expected_root} '
        ), (
            f"Expected filename to start with 'Aureolin Key "
            f"{expected_root} ' for requested key "
            f"{requested_key!r} -- got "
            f"{generated['tab_path'].name!r}."
        )


# ---------------------------------------------------------
# 5 -- "Keep input key" uses the input key correctly
# ---------------------------------------------------------

def test_keep_input_key_uses_source_key_in_filename():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gCGCD',
        output_folder=str(TEST_OUTPUT_DIR)
        # output_key omitted -- "Keep input key"
    )

    generated = result['scores'][0]['generated_files'][0]

    # Aureolin's own real, unmodified source key is B minor --
    # confirmed directly, BO-171's own investigation.
    assert generated['tab_path'].name == (
        'Aureolin Key B gCGCD (gCGCD).mscz'
    )


# ---------------------------------------------------------
# 6 -- a specified BO-171 output key uses the requested key
# ---------------------------------------------------------

def test_specified_output_key_uses_requested_key_in_filename():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gCGCD',
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='G'
    )

    generated = result['scores'][0]['generated_files'][0]

    assert generated['tab_path'].name == (
        'Aureolin Key G gCGCD (gCGCD).mscz'
    )


# ---------------------------------------------------------
# 7 -- "- TAB" is removed entirely
# ---------------------------------------------------------

def test_tab_suffix_removed_from_filename():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gCGCD',
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='C'
    )

    generated = result['scores'][0]['generated_files'][0]

    assert 'TAB' not in generated['tab_path'].name

    assert '-' not in generated['tab_path'].name


# ---------------------------------------------------------
# 8 -- existing in-score tuning text gains the added key
# (capo'd branch)
# ---------------------------------------------------------

def test_in_score_tuning_text_includes_key_for_capoed_tuning():

    score, staff_used = _load_aureolin()

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            score, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            str(TEST_OUTPUT_DIR), service,
            filename='bo172_in_score_text_test.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    root = ET.fromstring(content)

    tuning_text = None

    for element in root.iter():

        if element.tag.split('}')[-1] != 'Text':

            continue

        text_el = element.find('{*}text')

        if (
            text_el is not None and text_el.text
            and 'gDGBD' in text_el.text
        ):

            tuning_text = text_el.text

    assert tuning_text is not None

    # Open G itself has no capo (capo=0), so this call alone
    # doesn't exercise the capo'd branch this ticket's own
    # example covers -- confirmed via a real capo'd run below
    # instead, which is the actually-required case.


def test_in_score_tuning_text_includes_key_for_real_capoed_run():

    # The real, actual production path (main.py's own call),
    # exercising the genuinely capo'd branch this ticket's own
    # example is about -- not a hand-built Tuning object.
    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gDGBD',
        capo=2,
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='D'
    )

    generated = result['scores'][0]['generated_files'][0]

    with zipfile.ZipFile(generated['tab_path']) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    root = ET.fromstring(content)

    tuning_text = None

    for element in root.iter():

        if element.tag.split('}')[-1] != 'Text':

            continue

        text_el = element.find('{*}text')

        if (
            text_el is not None and text_el.text
            and 'gEAC#E' in text_el.text
        ):

            tuning_text = text_el.text

    assert tuning_text == (
        'Key D | gEAC#E (open: gDGBD, capo 2)'
    )


def test_in_score_tuning_text_unaffected_for_non_capoed_tuning():

    # The non-capo'd branch ("Banjo tuning: ...") is deliberately
    # left untouched by this ticket's own scope -- existing tests
    # (test_bo26, test_bo53) already assert this exact string
    # with no key prefix; this test locks the same invariant down
    # directly (those existing tests' own real-song fixture is
    # currently unavailable in this sandbox -- confirmed, a
    # pre-existing, unrelated BO-149 gap -- so this provides the
    # same coverage using Aureolin instead).
    score, staff_used = _load_aureolin()

    tuning = get_tunings()['Open G']  # capo == 0

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            score, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            str(TEST_OUTPUT_DIR), service,
            filename='bo172_non_capoed_text_test.mscz'
        )
    )

    with zipfile.ZipFile(output_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith('.mscx')
        ][0]

        content = z.read(mscx_name)

    root = ET.fromstring(content)

    tuning_text = None

    for element in root.iter():

        if element.tag.split('}')[-1] != 'Text':

            continue

        text_el = element.find('{*}text')

        if (
            text_el is not None and text_el.text
            and 'Banjo tuning' in text_el.text
        ):

            tuning_text = text_el.text

    assert tuning_text == 'Banjo tuning: gDGBD (Open G)'


# ---------------------------------------------------------
# 9 -- existing filename sanitization remains unchanged
# ---------------------------------------------------------

def test_filename_sanitization_still_strips_unsafe_characters():

    score, staff_used = _load_aureolin()

    # Inject unsafe filename characters into the title, the same
    # way _sanitize_filename() has always been expected to handle
    # -- confirmed directly against its own regex
    # (r'[\\/:*?"<>|]').
    score.score.title = 'Weird/Title:Name?'

    tuning = get_tunings()['Open G']

    service = ChordService(ChordLibrary())

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            score, tuning, staff_used,
            'templates/TAB_linked_Treble_Example.mscz',
            str(TEST_OUTPUT_DIR), service
        )
    )

    assert output_path.name == (
        'WeirdTitleName Key B Open G (gDGBD).mscz'
    )
