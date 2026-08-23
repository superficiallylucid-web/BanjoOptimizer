"""
tests/test_bo39_chord_shape_adjacent_position.py

Regression tests for BO-39: chord-shape selection now considers
the surrounding melody's playing position, not only the melody
note(s) occurring exactly at a chord's own onset.

Two distinct mechanisms, confirmed via direct investigation to
be genuinely different root causes before implementing either:

1. widening_pitches (chord_service.get_shapes_for_exact_melody_
   pitch()): when a chord has NO melody note at its own exact
   onset at all, the nearest surrounding melody pitches (before/
   after, regardless of whether either is itself a chord onset)
   are used to WIDEN candidate generation only -- reusing BO-20's
   own existing per-string widening mechanism unmodified, never
   treated as an onset-containment match. Real example: C7 at
   measure 18 (Double C/gCGCD) has no onset note; the desired
   high-position shape (0978, or the user's own suggested
   7-9-10-10) was never even generated without this.

2. preceding_chord_working_fret / following_chord_working_fret
   (same function): a new tiebreak positioned between quality_
   score and BO-33's existing onset-pitch-distance tiebreak --
   confirmed via direct testing that this specific placement is
   necessary (placing it after onset-pitch distance was tried
   and found insufficient: the real Am/G7 example never reaches
   it, since onset-pitch distance already resolves the tie
   first). When both preceding and following are given, a
   candidate's distance is the MINIMUM of its distance to each
   (not the maximum, unlike BO-30's own sandwiched-melody-note
   combination) -- confirmed via direct testing this, not max,
   produces the real Am/G7 example's own desired result. Real
   example: Am at measure 30 ties in quality between 0202
   (working_fret 2) and 0907 (working_fret 7); the following G7
   (working_fret 16, unavoidable given B4 has no low position in
   this tuning) pulls the tie toward 0907, forming a coherent
   phrase into G7 rather than an isolated low Am followed by an
   isolated, disconnected-feeling high G7.

Both signals apply ONLY among candidates already tied on
voicing_quality_score -- confirmed this never promotes a lower-
quality voicing over a higher-quality one, matching the priority
hierarchy: (1) existing validity/playability, (2) quality_score,
(3) adjacent-chord proximity, (4) BO-33's own onset-pitch
proximity, (5) existing remaining tiebreaks.

Two real, genuine cascading changes were found and confirmed
(not bugs) while validating this against the full regression
suite -- both updated honestly in their own test files after
confirming the new shape is genuinely quality-tied, not a lower-
quality voicing winning improperly:
  - A Modal Sawmill's Ddim (measures 5/13/29) moved from a high-
    position shape to the quality-tied 4534, correctly pulled
    toward its very-low Am/Em neighbors (test_bo35_fd_position_
    consistency.py updated).
  - Double C's Em (measure 2) moved from 4445 to the quality-
    tied 7979, correctly pulled toward its high Cmaj7 neighbor;
    BO-37's own preceding-FD-inclusion mechanism (measure 3's
    E4) remains fully intact, simply now operating on Em's new,
    legitimately-changed shape (test_bo37_preceding_fd_
    inclusion.py updated).

Confirmed via a whole-song scan that only 2 harmonies in the
entire real song have no onset melody note at all (the widening
path's own trigger condition) -- this is a rare, targeted
situation, not a broad change to candidate generation for
unrelated chords. Of those 2, only C7 (measure 18) actually
changed shape; Ddim (measure 32) stayed unchanged, confirming
widening does not disturb a chord whose existing shape is
already optimal.

Only chord_service.get_shapes_for_exact_melody_pitch()'s own
sort key and the new score_generator.py two-pass orchestration
in generate_tab_from_template() changed. Chord generation itself,
deduplication, voicing-quality calculation, playability rules,
FD exception handling, BO-20 exact-pitch matching, BO-21
exception detection, BO-24 fret continuity, BO-25 string
continuity, BO-30 bidirectional anchoring, BO-33's own onset-
pitch tiebreak, BO-35 multiple-FD-position consistency, and
BO-37/BO-38 melody continuity are all untouched.
"""

import os

import zipfile

import xml.etree.ElementTree as ET

from tunings import get_tunings

from parser import MuseScoreFile

from chord_service import ChordService

from chord_library import ChordLibrary

from fretboard import parse_shape, sounding_notes

from playing_model import _chord_working_fret

from score_generator import (
    _select_chord_shape_for_harmony, generate_tab_from_template
)


DOUBLE_C = get_tunings()["Double C"]  # gCGCD

TEMPLATE_PATH = "templates/TAB_linked_Treble_Example.mscz"

FULL_SONG_PATH = "The Christmas Song (notation only).mscz"


def _service():

    return ChordService(ChordLibrary())


# ---------------------------------------------------------
# 1 -- the real C7 case (widening_pitches, no onset note)
# ---------------------------------------------------------

def test_real_c7_widening_produces_high_position_shape():

    service = _service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_C, "C", 0, "7", "Dominant 7th", set(),
        following_chord_working_fret=7,
        widening_pitches={70}  # A#4, the real surrounding pitch
    )

    values = parse_shape(shapes[0].shape)

    assert _chord_working_fret(values) == 7


# ---------------------------------------------------------
# 2 -- the real Am/G7 case
# ---------------------------------------------------------

def test_real_am_prefers_higher_position_toward_g7():

    service = _service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_C, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2,
        preceding_chord_working_fret=5,  # Ddim
        following_chord_working_fret=16  # G7
    )

    assert shapes[0].shape == "0907"


# ---------------------------------------------------------
# 3 -- control: the existing low-position shape must remain
# preferred when no adjacent-chord signal is given at all
# ---------------------------------------------------------

def test_no_adjacent_signal_preserves_existing_low_shape():

    service = _service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_C, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2
        # no preceding/following_chord_working_fret at all
    )

    assert shapes[0].shape == "0202"


# ---------------------------------------------------------
# 4 -- an exact FD/melody requirement must still override
# positional preference entirely (this branch returns before
# any of the new signals are ever consulted)
# ---------------------------------------------------------

def test_exact_fd_requirement_unaffected_by_adjacent_chord():

    from score_generator import _choose_melody_position

    open_notes = DOUBLE_C.notes[1:]

    cmaj7_fd = parse_shape("0978")

    chosen = _choose_melody_position(
        70, open_notes, fd_shape_values=cmaj7_fd
        # adjacent-chord signals don't even apply to melody-
        # position selection -- confirms this is a separate
        # system from chord-shape selection entirely, and BO-20's
        # own exact-pitch/FD requirement is never touched by it
    )

    assert chosen["fret"] == 8

    assert chosen["string"] == 3


# ---------------------------------------------------------
# 5 -- quality-tied conflict: adjacent-chord proximity favors
# one candidate, onset-pitch proximity favors the other --
# the new priority (adjacent-chord first) must win
# ---------------------------------------------------------

def test_quality_tied_conflict_adjacent_chord_wins():

    service = _service()

    # Real Am case again, but with preferred_melody_fret set to
    # exactly match 0202's own E4 position (fret 2) -- BO-33's
    # own onset-pitch tiebreak would strongly favor 0202 here
    # (distance 0) over 0907 (distance far higher), while the
    # adjacent-chord signal favors 0907. Confirms the NEW
    # priority (adjacent-chord before onset-pitch) decides.
    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_C, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2,  # favors 0202 (exact match)
        preceding_chord_working_fret=5,
        following_chord_working_fret=16  # favors 0907
    )

    assert shapes[0].shape == "0907", (
        "adjacent-chord proximity must be consulted BEFORE "
        "onset-pitch proximity for quality-tied candidates -- "
        "0202 would win if onset-pitch distance were checked "
        "first, since preferred_melody_fret=2 exactly matches it"
    )


# ---------------------------------------------------------
# 6 -- reverse control: when the adjacent chord is ITSELF low
# (agreeing with onset-pitch proximity, not conflicting), the
# existing BO-33 choice is unaffected -- both signals agree
# ---------------------------------------------------------

def test_agreeing_adjacent_chord_does_not_change_bo33_choice():

    service = _service()

    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_C, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2,
        preceding_chord_working_fret=2,  # also low -- agrees
        following_chord_working_fret=2  # also low -- agrees
    )

    assert shapes[0].shape == "0202"


# ---------------------------------------------------------
# 7 -- quality is never sacrificed for adjacent-chord
# proximity (the explicit priority-hierarchy requirement)
# ---------------------------------------------------------

def test_adjacent_chord_never_beats_higher_quality():

    service = _service()

    # An extreme following anchor that would favor a much lower-
    # quality candidate if quality weren't checked first.
    shapes = service.get_shapes_for_exact_melody_pitch(
        DOUBLE_C, "A", 9, "m", "Minor", {64},
        preferred_melody_fret=2,
        following_chord_working_fret=21
    )

    assert shapes[0].voicing_quality_score == max(
        s.voicing_quality_score for s in shapes
    )


# ---------------------------------------------------------
# 8 -- full pipeline: both real examples, end to end, plus
# FD/TAB consistency intact
# ---------------------------------------------------------

def test_full_pipeline_real_examples_and_consistency():

    p = MuseScoreFile(FULL_SONG_PATH)

    p.open()

    p.read_title()

    p.read_time_signature()

    staff_used = p.read_melody_notes()

    p.read_harmonies(staff_used)

    service = _service()

    output_path, applied, skipped, exceptions = (
        generate_tab_from_template(
            p, DOUBLE_C, staff_used, TEMPLATE_PATH, "output",
            service, filename="test_bo39_pipeline.mscz"
        )
    )

    try:

        assert applied == 56

        assert skipped == 0

        assert exceptions == []

        with zipfile.ZipFile(output_path) as archive:

            mscx_name = [
                n for n in archive.namelist()
                if n.endswith(".mscx")
            ][0]

            xml_bytes = archive.read(mscx_name)

        root = ET.fromstring(xml_bytes)

        staff = root.find('.//{*}Score/{*}Staff[@id="1"]')

        fret_diagrams = staff.findall(".//{*}FretDiagram")

        assert len(fret_diagrams) == 56

        for fd in fret_diagrams:

            assert fd.find("{*}color") is None

        measures = staff.findall("{*}Measure")

        # measure 18's real, confirmed C7 case
        m18_voice = list(measures[17].find("{*}voice"))

        c7_fd = next(
            el for el in m18_voice
            if el.tag.split("}")[-1] == "FretDiagram"
        )

        c7_offset = int(c7_fd.find("{*}fretOffset").text)

        assert c7_offset == 6  # 0978, working_fret 7

        # measure 30's real, confirmed Am case (second FD)
        m30_voice = list(measures[29].find("{*}voice"))

        am_fds = [
            el for el in m30_voice
            if el.tag.split("}")[-1] == "FretDiagram"
        ]

        am_offset = int(am_fds[1].find("{*}fretOffset").text)

        assert am_offset == 6  # 0907, working_fret 7

    finally:

        if os.path.exists(output_path):

            os.remove(output_path)
