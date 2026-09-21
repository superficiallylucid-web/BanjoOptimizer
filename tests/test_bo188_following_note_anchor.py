"""
tests/test_bo188_following_note_anchor.py

Regression tests for BO-188: barring other rules that dictate a
specific location, a melody note should be placed on the string
and fret that best matches the tab immediately before or after
it. "Immediately before" was already handled by the existing
previous_position mechanism; this BO adds the "immediately
after" side for the one case that's both tractable and safe to
generalize without a full two-pass solve: a chain of one or more
consecutive, single-note melody events that all share the EXACT
SAME pitch. Since the pitch is identical, the exact same string/
fret candidates are valid for every note in the chain, so
propagating a later note's own real anchor backward through the
whole chain is safe -- no need to actually resolve any note's
position in advance.

The existing following_working_fret_anchor_by_event_id (BO-30)
only ever looked exactly one event ahead, so only the single
note immediately preceding a chord onset picked up that onset's
working fret as its own following anchor. An earlier note in a
run of repeated identical pitches got no anchor at all and fell
through to best_position()'s own plain low-fret preference, even
though the exact same string/fret candidates were available to
it as to the note right after it.

Real, reported case: Let It Snow / aEADE (gDGCD capo 2, 5th
string A, key F), measure 1, beat 1: a C4 (pitch 60) with no
anchor of its own, immediately followed by a second, IDENTICAL
C4 that DOES have a real following anchor (the chord at beat
1.0) and correctly lands on fret 8. The preferred tab keeps both
on the same fret -- this is exactly BO-187's own row 1, left
unaddressed there since BO-187's own fix (the anchor's "at or
above" semantics) can't help a note with no anchor at all.
"""

import sys

sys.path.insert(0, '.')

import zipfile

import xml.etree.ElementTree as ET

from score_generator import _choose_melody_position

from tunings import get_tunings

from conftest import fixture_path, TEST_OUTPUT_DIR

import main


A_MODAL_SAWMILL = get_tunings()["A Modal Sawmill"]  # aEADE

OPEN_NOTES = A_MODAL_SAWMILL.notes[1:]  # 4th to 1st


# ---------------------------------------------------------
# 1 -- the decision function itself, in isolation: a note WITH
#      a real following anchor still behaves exactly as before
#      (BO-188 only adds a new SOURCE for this same parameter,
#      not new logic inside _choose_melody_position() itself)
# ---------------------------------------------------------

def test_following_anchor_still_works_directly():

    chosen = _choose_melody_position(
        60, OPEN_NOTES, following_working_fret_anchor=7
    )

    assert chosen["fret"] == 8


# ---------------------------------------------------------
# 2 -- the real, reported case: Let It Snow / aEADE, measure 1
# ---------------------------------------------------------

def _generate():

    return main.run_optimizer(
        score_path=str(fixture_path("Let_It_Snow.mscz")),
        tuning_symbol="gDGCD",
        capo=2,
        fifth_string="A",
        output_key="F",
        output_folder=str(TEST_OUTPUT_DIR)
    )


def _measure_1_notes(tab_path):

    with zipfile.ZipFile(tab_path) as z:

        mscx_name = [
            n for n in z.namelist() if n.endswith(".mscx")
        ][0]

        content = z.read(mscx_name)

    root = ET.fromstring(content)

    for staff in root.iter():

        if (
            staff.tag.split("}")[-1] == "Staff"
            and staff.attrib.get("id") == "1"
        ):

            measure_1 = staff.findall("{*}Measure")[0]

            notes = []

            for note in measure_1.iter():

                if note.tag.split("}")[-1] != "Note":

                    continue

                fret_el = note.find("{*}fret")

                string_el = note.find("{*}string")

                pitch_el = note.find("{*}pitch")

                if fret_el is not None:

                    notes.append(
                        (
                            int(pitch_el.text),
                            int(fret_el.text),
                            int(string_el.text)
                        )
                    )

            return notes

    return None


def test_real_let_it_snow_first_note_matches_following_identical_pitch(
):

    result = _generate()

    gen = result["scores"][0]["generated_files"][0]

    notes = _measure_1_notes(gen["tab_path"])

    # The very first note of the piece (pitch 60, no chord anchor
    # of its own) and the second, identical-pitch-60 note right
    # after it (which DOES have a real following anchor) both
    # land on fret 8, XML string 3 (external 4th string) --
    # confirmed matching, not merely both present somewhere.
    pitch_60_notes = [n for n in notes if n[0] == 60]

    assert len(pitch_60_notes) == 2

    for pitch, fret, string in pitch_60_notes:

        assert (fret, string) == (8, 3)


def test_backward_propagation_stops_at_real_chord_onset():

    # A note that's immediately followed by a genuine chord onset
    # (not a repeated-pitch chain) must keep using that onset's
    # own real working fret, unaffected by this BO -- confirmed
    # via the pitch-70 note from BO-187's own row 2, which sits
    # right before the same chord onset this backward-propagation
    # pass must not disturb.
    result = _generate()

    gen = result["scores"][0]["generated_files"][0]

    notes = _measure_1_notes(gen["tab_path"])

    pitch_70_notes = [n for n in notes if n[0] == 70]

    assert len(pitch_70_notes) == 1

    _, fret, string = pitch_70_notes[0]

    assert (fret, string) == (8, 1)
