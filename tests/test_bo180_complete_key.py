"""
tests/test_bo180_complete_key.py

Regression tests for BO-180: the "output key" shown in the
generated filename, the in-score tuning text label, and the
GUI's own per-tuning result line is now the COMPLETE key (root
note + "m" suffix for minor, e.g. "Bm" -- major stays root-only,
e.g. "C") via the new music.key_display_name() helper, replacing
BO-172's own root-only convention, which conflated two different,
genuine keys (e.g. B major and B minor) into the same displayed
text ("Key B" either way).

Real fixture used: Aureolin.mscz, whose own real, unmodified
source key is B minor (confirmed directly, BO-171's own
investigation, and reused throughout test_bo172_key_in_
filename.py).
"""

import sys

sys.path.insert(0, '.')

import main

from music import key_display_name

from conftest import fixture_path, TEST_OUTPUT_DIR


# ---------------------------------------------------------
# 1 -- music.key_display_name() itself
# ---------------------------------------------------------

def test_minor_key_gets_m_suffix():

    assert key_display_name("B minor") == "Bm"

    assert key_display_name("F# minor") == "F#m"

    assert key_display_name("Bb minor") == "Bbm"


def test_major_key_stays_root_only():

    assert key_display_name("C major") == "C"

    assert key_display_name("F# major") == "F#"


def test_mode_word_case_insensitive():

    assert key_display_name("B MINOR") == "Bm"

    assert key_display_name("B Minor") == "Bm"


def test_falsy_key_returns_empty_string():

    assert key_display_name("") == ""

    assert key_display_name(None) == ""


def test_single_word_key_defaults_to_major_unmarked():

    # "Unknown" -- parser.MuseScoreFile's own default when key
    # estimation never ran -- has no mode word at all; treated as
    # major (unmarked), matching every existing "Unknown" caller's
    # prior root-only behavior exactly (score_file.key.split()[0]
    # on "Unknown" was already just "Unknown").
    assert key_display_name("Unknown") == "Unknown"


# ---------------------------------------------------------
# 2 -- filename uses the complete key (real minor source)
# ---------------------------------------------------------

def test_filename_shows_m_suffix_for_minor_source():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gCGCD',
        output_folder=str(TEST_OUTPUT_DIR)
        # output_key omitted -- "Keep input key" (B minor)
    )

    generated = result['scores'][0]['generated_files'][0]

    assert generated['tab_path'].name == (
        'Aureolin Key Bm gCGCD (gCGCD).mscz'
    )


def test_filename_shows_m_suffix_for_transposed_output_key():

    # Transposition preserves mode (transpose_score()'s own
    # docstring/behavior) -- a minor source stays minor after
    # being moved to a different requested root.
    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gCGCD',
        output_folder=str(TEST_OUTPUT_DIR),
        output_key='G'
    )

    generated = result['scores'][0]['generated_files'][0]

    assert generated['tab_path'].name == (
        'Aureolin Key Gm gCGCD (gCGCD).mscz'
    )


# ---------------------------------------------------------
# 3 -- in-score tuning text label uses the complete key too
# ---------------------------------------------------------

def test_in_score_capoed_text_shows_m_suffix():

    import zipfile

    import xml.etree.ElementTree as ET

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
        'Key Dm | gEAC#E (open: gDGBD, capo 2)'
    )


# ---------------------------------------------------------
# 4 -- GUI per-tuning line shows a complete key, always (not
#      only in any-key mode) -- exercised as _display_result's
#      own string-building logic, not a real Qt widget
# ---------------------------------------------------------

def _build_per_tuning_lines(score_result):

    # Mirrors gui.py's own MainWindow._display_result() logic
    # exactly (same source lines, without a real QTextEdit) --
    # kept in sync manually since gui.py isn't importable in a
    # headless test environment (no PySide6 display available).
    mode_word = (
        score_result["key"].split()[-1]
        if score_result["key"] else ""
    )

    lines = []

    for i, rec in enumerate(
        score_result["recommendations"], start=1
    ):

        display_key = key_display_name(
            f"{rec.recommended_key} {mode_word}"
            if rec.recommended_key is not None
            else score_result["key"]
        )

        key_suffix = (
            f" [Key: {display_key}]" if display_key else ""
        )

        lines.append(
            f"{i}. {rec.name} ({rec.symbol}){key_suffix}"
        )

    return lines


def test_gui_line_shows_key_in_same_key_mode():

    # Same-key mode: BO-178's own recommended_key is never set
    # (always None), yet BO-180 requires the key to display here
    # too -- falls back to this score's own key.
    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        tuning_symbol='gCGCD',
        capo=2,
        output_folder=str(TEST_OUTPUT_DIR)
    )

    lines = _build_per_tuning_lines(result["scores"][0])

    assert len(lines) == 1

    assert "[Key: Bm]" in lines[0]


def test_gui_line_shows_key_per_tuning_in_any_key_mode():

    result = main.run_optimizer(
        score_path=str(fixture_path('Aureolin.mscz')),
        output_folder=str(TEST_OUTPUT_DIR),
        any_key=True,
        num_tunings=3
    )

    lines = _build_per_tuning_lines(result["scores"][0])

    assert len(lines) == 3

    # Every line has SOME complete key shown -- not just the
    # tunings whose own best key happened to differ from the
    # source (BO-180's own point: this used to be omitted for
    # the others).
    for line in lines:

        assert "[Key: " in line

        # Never a bare root with no "m"/"major" distinction lost
        # -- Aureolin's source is minor, and every candidate key
        # here is reached by transposing it, so every one must
        # show minor's own "m" suffix.
        assert "m]" in line
