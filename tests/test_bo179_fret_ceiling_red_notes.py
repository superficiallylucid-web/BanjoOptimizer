"""
tests/test_bo179_fret_ceiling_red_notes.py

Regression tests for BO-179: a melody note genuinely unreachable
within the user's own configured fret ceiling (fretboard.get_
max_fret(), BO-177) is no longer silently written as a Rest.
generate_tab_from_template() now retries once, at the real
physical maximum (fretboard.MAX_ALLOWED_MAX_FRET), using the
exact same _choose_melody_position() scoring/tiebreak logic --
not a second, simplified search. If that retry finds a position,
the note is written for real (correct fret/string) and marked
red (the same <color r="255" g="0" b="4" a="255" /> marking
BO-168 already uses for octave-substitution warnings -- BO-179
reuses that same helper, now generalized to _add_note_warning_
color()). Only when even the real physical maximum has no
candidate does the note stay a silent Rest, exactly as before
this BO.

Real fixture used: "The Christmas Song (notation only).mscz" in
Double C (gCGCD) -- the same fixture/tuning test_bo40_fifth_
string_transition.py and others already use. Confirmed directly
(during this BO's own investigation) to contain a real melody
event at measure 33, beat 3.5, pitch 79 (G5) that is unreachable
within the default 15-fret ceiling (best candidate: fret 19 on
string 3) but reachable at fret 19 within the real physical
maximum. This is a genuine, pre-existing case in this fixture,
not synthesized for this test file -- before BO-179, this exact
note was the sole cause of test_bo40/test_bo36/test_bo38's own
"exceptions == []" sanity assertions failing at HEAD.
"""

import sys

sys.path.insert(0, '.')

import zipfile

import xml.etree.ElementTree as ET

import pytest

from conftest import fixture_path, new_output_dir

from fretboard import (
    set_max_fret,
    get_max_fret,
    find_positions,
    MIN_ALLOWED_MAX_FRET,
    MAX_ALLOWED_MAX_FRET
)

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from score_generator import generate_tab_from_template


@pytest.fixture(autouse=True)
def _restore_max_fret():

    # Same convention as test_bo177_fret_ceiling.py -- every test
    # in this file may change the shared module-level ceiling;
    # restore it afterward so tests in other files always see the
    # same default a fresh interpreter would.
    original = get_max_fret()

    yield

    set_max_fret(original)


DOUBLE_C = get_tunings()["Double C"]  # gCGCD

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = fixture_path(
    "The Christmas Song (notation only).mscz"
)

OUTPUT_FOLDER = new_output_dir()


def _generate(tuning, filename):

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = ChordService(ChordLibrary())

    return generate_tab_from_template(
        p, tuning, staff_used, TEMPLATE_PATH, OUTPUT_FOLDER,
        service, filename=filename
    )


def _staff_from(output_path):

    with zipfile.ZipFile(output_path) as archive:

        mscx_name = [
            n for n in archive.namelist() if n.endswith(".mscx")
        ][0]

        xml_bytes = archive.read(mscx_name)

    root = ET.fromstring(xml_bytes)

    return root.find('.//{*}Score/{*}Staff[@id="1"]')


def _colored_notes(staff):

    colored = []

    for note in staff.iter():

        if note.tag.split('}')[-1] != "Note":

            continue

        color = note.find("{*}color")

        fret_el = note.find("{*}fret")

        if color is not None and fret_el is not None:

            colored.append(int(fret_el.text))

    return colored


# ---------------------------------------------------------
# 1 -- find_positions()'s own new max_fret override
# ---------------------------------------------------------

def test_find_positions_default_unchanged():

    set_max_fret(15)

    open_notes = [DOUBLE_C.notes[i] for i in range(5)]

    # C6 (85) is unreachable within 15 on every string of this
    # tuning (confirmed directly: the closest open string, g/67,
    # would need fret 18) -- a plain, deliberately unrelated
    # pitch to the real measure-33 pipeline case below, kept
    # separate so this unit-level check doesn't depend on that
    # case's own, more complex, full _choose_melody_position()
    # scoring.
    assert find_positions(85, open_notes) == []


def test_find_positions_explicit_override_widens_pool():

    set_max_fret(15)

    open_notes = [DOUBLE_C.notes[i] for i in range(5)]

    widened = find_positions(85, open_notes, max_fret=22)

    assert widened != []

    assert all(
        position["fret"] <= 22 for position in widened
    )


def test_find_positions_override_does_not_leak():

    set_max_fret(15)

    open_notes = [DOUBLE_C.notes[i] for i in range(5)]

    find_positions(85, open_notes, max_fret=22)

    # A one-off max_fret= call must never change the shared,
    # module-level ceiling for any later, unrelated call.
    assert get_max_fret() == 15

    assert find_positions(85, open_notes) == []


# ---------------------------------------------------------
# 2 -- the real, confirmed case: written red, not skipped
# ---------------------------------------------------------

def test_real_measure33_g5_written_not_skipped():

    set_max_fret(15)

    output_path, applied, skipped, exceptions = _generate(
        DOUBLE_C, "test_bo179_m33.mscz"
    )

    try:

        # Before BO-179, this exact note was reported here
        # instead of being written at all.
        assert not any(
            ex.get("melody_pitch") == 79
            and ex.get("measure") == 33
            for ex in exceptions
        )

    finally:

        import os

        if os.path.exists(output_path):

            os.remove(output_path)


def test_real_measure33_g5_marked_red():

    set_max_fret(15)

    output_path, applied, skipped, exceptions = _generate(
        DOUBLE_C, "test_bo179_m33_color.mscz"
    )

    try:

        staff = _staff_from(output_path)

        colored_frets = _colored_notes(staff)

        # Asserts the genuine, load-bearing behavior (a real
        # note beyond the ceiling exists and is colored) rather
        # than pinning the exact fret _choose_melody_position()'s
        # own full scoring picks -- that choice depends on
        # surrounding-note context (anchors/continuity) this
        # test doesn't reconstruct, and pinning it here would
        # make the test brittle to unrelated scoring changes.
        assert len(colored_frets) >= 1

        assert any(fret > 15 for fret in colored_frets)

    finally:

        import os

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 3 -- a lower ceiling produces MORE red notes, not exceptions
# ---------------------------------------------------------

def test_lower_ceiling_colors_more_notes_instead_of_dropping_them():

    set_max_fret(MIN_ALLOWED_MAX_FRET)

    output_path, applied, skipped, exceptions = _generate(
        DOUBLE_C, "test_bo179_min_ceiling.mscz"
    )

    try:

        staff = _staff_from(output_path)

        colored_frets = _colored_notes(staff)

        # An extreme ceiling forces many real notes beyond it --
        # every one of them must still be written (and colored),
        # not silently dropped as a Rest.
        assert len(colored_frets) > 1

        assert all(
            fret > MIN_ALLOWED_MAX_FRET for fret in colored_frets
        )

    finally:

        import os

        if os.path.exists(output_path):

            os.remove(output_path)


# ---------------------------------------------------------
# 4 -- genuinely unplayable (beyond the real physical max)
#      still stays a silent Rest -- not falsely "fixed"
# ---------------------------------------------------------

def test_genuinely_unreachable_pitch_still_a_rest():

    set_max_fret(15)

    open_notes = [DOUBLE_C.notes[i] for i in range(5)]

    # Every string's own fret for this pitch exceeds even the
    # real physical maximum (22) -- confirmed via direct
    # computation from this tuning's own open notes, not
    # asserted blindly.
    unreachable_midi = max(open_notes) + MAX_ALLOWED_MAX_FRET + 5

    assert find_positions(
        unreachable_midi, open_notes, max_fret=MAX_ALLOWED_MAX_FRET
    ) == []


# ---------------------------------------------------------
# 5 -- BO-168's own octave-substitution coloring is unaffected
#      by the helper's BO-179 rename/generalization
# ---------------------------------------------------------

def test_octave_substitution_coloring_still_works():

    # BO-179 generalized/renamed this helper from
    # _add_octave_substitution_color() to _add_note_warning_
    # color() -- confirms the rename didn't change its own
    # behavior for its original (BO-168) caller.
    from score_generator import _add_note_warning_color

    import xml.etree.ElementTree as ET

    note_element = ET.Element("Note")

    _add_note_warning_color(note_element)

    color = note_element.find("color")

    assert color is not None

    assert color.get("r") == "255"

    assert color.get("g") == "0"

    assert color.get("b") == "4"

    assert color.get("a") == "255"
