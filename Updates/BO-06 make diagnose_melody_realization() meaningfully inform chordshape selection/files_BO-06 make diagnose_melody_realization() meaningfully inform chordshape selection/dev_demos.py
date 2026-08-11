"""
dev_demos.py

All of Banjo Optimizer's temporary diagnostic/architecture-
validation demos, moved out of main.py so a normal run of the
tool isn't buried under ~9 diagnostic sections before the
actual tuning report. This file is exactly that code, relocated
-- no demo logic changed, nothing removed, nothing renamed.

Run standalone for development:

    python dev_demos.py

Or from main.py with the --demos flag:

    python main.py --demos

Each block is still individually labeled "(temporary)" in its
own output, same as before -- this file is itself meant to be
trimmed or reorganized further once the architecture is fully
stable, not a permanent home for these demos.
"""

from pathlib import Path

from output import output

from parser import MuseScoreFile
from chord_library import ChordLibrary
from chord_generator import generate_candidates
from chord_service import ChordService, diagnose_melody_realization
from playability import evaluate as evaluate_playability
from tunings import get_tunings
from music import (
    note_name_to_pitch_class,
    midi_to_note_name,
    pitch_name
)
from fretboard import (
    sounding_notes,
    find_melody_occurrences,
    calculate_shape_metadata
)

PROJECT_FOLDER = Path(__file__).parent

SCORES_FOLDER = PROJECT_FOLDER / "scores"


def run_all_demos():
    """
    Runs every temporary demo block, in the same order and
    with the same output they've always had.
    """

    # ---------------------------------------------------------
    # TEMPORARY: chord library architecture demo
    # ---------------------------------------------------------
    #
    # Validates ChordLibrary / ChordShape only -- not connected
    # to scoring or recommendations yet. Safe to delete this
    # block once real integration exists.

    output("--- Chord Library Demo (temporary) ---")

    chord_library = ChordLibrary()

    chord_library.load(
        "banjo_chord_library - gDGBD Chord Shapes.csv"
    )

    for demo_root, demo_quality in [
        ("C", "Major"),
        ("G", "Major"),
        ("E", "Major"),
    ]:

        matches = chord_library.find(
            "gDGBD",
            demo_root,
            demo_quality
        )

        output(f"{demo_root} {demo_quality}:")

        for match in matches:

            output(
                f"   shape={match.shape}",
                f"comfort={match.comfort_code}",
                f"({match.comfort_explanation})"
            )

    output("--- End Chord Library Demo ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: chord library statistics demo
    # ---------------------------------------------------------
    #
    # Development/validation only -- lets you check how complete
    # the library is as more tunings and shapes get filled in.
    # Not connected to scoring or the report. Safe to delete this
    # block once it's no longer needed for validation.

    output("--- Chord Library Statistics (temporary) ---")

    stats = chord_library.statistics()

    output(f"Tuning files loaded: {stats['tunings_loaded']}")

    for tuning_symbol, tuning_stats in stats["by_tuning"].items():

        output(f"\n{tuning_symbol}:")

        output(f"  Total shapes: {tuning_stats['total']}")

        output(f"  Verified: {tuning_stats['verified']}")

        output(
            "  Candidate (unverified):",
            tuning_stats['candidate']
        )

        output(
            "  Unspecified verification:",
            tuning_stats['unspecified']
        )

        output("  By quality:")

        for quality, count in tuning_stats["by_quality"].items():

            output(f"    {quality}: {count}")

    totals = stats["totals"]

    output("\nGrand totals:")

    output(f"  Total shapes: {totals['total']}")

    output(f"  Verified: {totals['verified']}")

    output("  Candidate (unverified):", totals['candidate'])

    output(
        "  Unspecified verification:",
        totals['unspecified']
    )

    output("  By quality:")

    for quality, count in totals["by_quality"].items():

        output(f"    {quality}: {count}")

    output("--- End Chord Library Statistics ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: chord generator demo
    # ---------------------------------------------------------
    #
    # Shows the generator's candidates for a few Major chords in
    # Open G, labeled full vs. reduced/rescue so it's obvious at a
    # glance which voicings are the default (full) and which only
    # exist because a full voicing was impractical (reduced/
    # rescue). Not connected to scoring or the report. Safe to
    # delete this block once it's no longer needed.

    output("--- Chord Generator Demo (temporary) ---")

    open_g = get_tunings()["Open G"]

    for demo_root, demo_root_pc, demo_quality in [
        ("C", 0, "Major"),
        ("G", 7, "Major"),
        ("E", 4, "Major"),
    ]:

        generated_matches = generate_candidates(
            tuning=open_g,
            root=demo_root,
            root_pc=demo_root_pc,
            quality_code="",
            quality_display=demo_quality
        )

        output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

        for match in generated_matches:

            voicing_type = (
                "reduced/rescue" if "--" in match.shape else "full"
            )

            output(
                f"    {match.shape:<8}",
                f" {voicing_type:<15}",
                f" {match.inversion}, top {match.top_note}"
            )

    output("\n--- End Chord Generator Demo ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: inversion / top note demo
    # ---------------------------------------------------------
    #
    # Shows, for each generated candidate, its shape, identified
    # inversion, and the highest-sounding note in that voicing.
    # Not used in scoring or ranking -- this is groundwork for
    # future melody-note matching. Not connected to the report.
    # Safe to delete this block once it's no longer needed.

    output("--- Inversion / Top Note Demo (temporary) ---")

    for demo_root, demo_root_pc, demo_quality in [
        ("C", 0, "Major"),
        ("G", 7, "Major"),
        ("E", 4, "Major"),
    ]:

        generated_matches = generate_candidates(
            tuning=open_g,
            root=demo_root,
            root_pc=demo_root_pc,
            quality_code="",
            quality_display=demo_quality
        )

        output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

        for match in generated_matches:

            output(
                f"    {match.shape}",
                f" {match.inversion}",
                f" (top note: {match.top_note})"
            )

    output("\n--- End Inversion / Top Note Demo ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: playability filter demo
    # ---------------------------------------------------------
    #
    # Shows every RAW generated candidate (before chord_service's
    # filtering) run through playability.evaluate() individually,
    # so both accepted and rejected shapes are visible side by
    # side with their score and reason. This is the unfiltered
    # view -- the chord service demo below shows what's left
    # after rejected candidates are already removed. Not
    # connected to scoring or the report. Safe to delete this
    # block once it's no longer needed.

    output("--- Playability Filter Demo (temporary) ---")

    for demo_root, demo_root_pc, demo_quality in [
        ("C", 0, "Major"),
        ("G", 7, "Major"),
        ("E", 4, "Major"),
    ]:

        raw_candidates = generate_candidates(
            tuning=open_g,
            root=demo_root,
            root_pc=demo_root_pc,
            quality_code="",
            quality_display=demo_quality
        )

        output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

        for candidate in raw_candidates:

            result = evaluate_playability(candidate.shape)

            status = "ACCEPTED" if result.accepted else "REJECTED"

            output(
                f"    {candidate.shape}  {status}",
                f" score={result.score}",
                f" - {result.reason}"
            )

            for warning in result.warnings:

                output(f"        warning: {warning}")

    output("\n--- End Playability Filter Demo ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: chord service demo
    # ---------------------------------------------------------
    #
    # Shows ChordService's merged, deduplicated output for a few
    # sample chords -- verified shapes first (library order),
    # then generated candidates that aren't already covered by a
    # verified shape. No ranking logic beyond that ordering yet
    # (see chord_service.py's docstring for what's deliberately
    # left out). Not connected to scoring or the report. Safe to
    # delete this block once it's no longer needed.

    output("--- Chord Service Demo (temporary) ---")

    chord_service = ChordService(chord_library)

    for demo_root, demo_root_pc, demo_quality in [
        ("C", 0, "Major"),
        ("G", 7, "Major"),
        ("E", 4, "Major"),
    ]:

        merged = chord_service.get_shapes(
            tuning=open_g,
            root=demo_root,
            root_pc=demo_root_pc,
            quality_code="",
            quality_display=demo_quality
        )

        output(f"\n{demo_root} {demo_quality} in Open G (gDGBD):")

        for rank, shape in enumerate(merged, start=1):

            output(
                f"    {rank}. {shape.shape}",
                f"[{shape.source}]"
            )

    output("\n--- End Chord Service Demo ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: melody / chord shape demo
    # ---------------------------------------------------------
    #
    # Shows get_shapes_for_melody() reordering the same merged
    # list from the Chord Service Demo above to prefer shapes
    # that sound a given melody note anywhere -- not just as the
    # top note (see get_shapes_for_melody's own docstring). Calls
    # the real ChordService -- nothing here is hard-coded. Not
    # connected to scoring, the report, or tuning recommendations.
    # Safe to delete this block once it's no longer needed.

    output("--- Melody / Chord Shape Demo (temporary) ---")

    for melody_note in ["E", "D"]:

        shapes = chord_service.get_shapes_for_melody(
            tuning=open_g,
            root="C",
            root_pc=0,
            quality_code="",
            quality_display="Major",
            melody_note=melody_note
        )

        output(f"\nC Major, melody note {melody_note}:")

        for rank, shape in enumerate(shapes, start=1):

            occurrences = find_melody_occurrences(
                open_g, shape.shape, melody_note
            )

            match_label = ""

            if occurrences:

                locations = ", ".join(
                    f"string {o.string_index}" for o in occurrences
                )

                match_label = f"  MELODY MATCH ({locations})"

            output(
                f"    {rank}. {shape.shape}",
                f"[{shape.source}]",
                f" top={shape.top_note}{match_label}"
            )

    # Real-data check: pull a real chord occurrence and its melody
    # note from an actual tracked score (White Christmas has real
    # Harmony/chord-symbol data), then feed that real root/quality/
    # melody note straight into the real ChordService ranking --
    # nothing in this block is hard-coded, all of it comes from
    # parsing the actual file.
    output("\nReal-data check (White Christmas):")

    white_christmas = MuseScoreFile(
        SCORES_FOLDER / "White Christmas (G (gCGBD)).mscz"
    )

    white_christmas.open()
    white_christmas.read_time_signature()
    white_christmas.read_melody_notes()
    white_christmas.read_harmonies(4)

    major_harmony = None

    for harmony in white_christmas.score.harmonies:

        if harmony.quality_code == "":

            major_harmony = harmony

            break

    if major_harmony is not None:

        root_name = pitch_name(major_harmony.root_pc)

        melody_midi = white_christmas.score.melody_note_for_harmony(
            major_harmony
        )

        melody_note_name = (
            midi_to_note_name(melody_midi)
            if melody_midi is not None
            else None
        )

        output(
            f"    Measure {major_harmony.measure}: "
            f"{major_harmony.symbol} -- melody note "
            f"{melody_note_name or '(none found)'}"
        )

        if melody_note_name is not None:

            real_shapes = chord_service.get_shapes_for_melody(
                tuning=open_g,
                root=root_name,
                root_pc=major_harmony.root_pc,
                quality_code="",
                quality_display="Major",
                melody_note=melody_note_name
            )

            for rank, shape in enumerate(real_shapes, start=1):

                output(
                    f"      {rank}. {shape.shape}",
                    f"[{shape.source}]",
                    f" top={shape.top_note}"
                )

    else:

        output(
            "    No Major-quality chord found in this score's "
            "Harmony data."
        )

    output("\n--- End Melody / Chord Shape Demo ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: melody occurrence demo
    # ---------------------------------------------------------
    #
    # Shows that "melody match" and "top note match" are NOT the
    # same question. find_melody_occurrences() checks every
    # sounding string, not just the highest -- this uses a shape
    # where the melody note occurs on an inner voice, so it's
    # obvious the two concepts differ. Not connected to ranking,
    # scoring, or the report -- this only demonstrates the new
    # detection capability itself (see get_shapes_for_melody's
    # docstring for why ranking hasn't changed yet). Safe to
    # delete this block once it's no longer needed.

    output("--- Melody Occurrence Demo (temporary) ---")

    demo_shape = "0000"

    demo_melody_note = "B"

    all_notes = sounding_notes(open_g, demo_shape)

    _, demo_top_note = calculate_shape_metadata(
        open_g, demo_shape, 7, ""
    )

    occurrences = find_melody_occurrences(
        open_g, demo_shape, demo_melody_note
    )

    output(f"\nG Major shape: {demo_shape}")

    output(
        "  All sounding notes:",
        ", ".join(n.name for n in all_notes)
    )

    output(f"  top_note: {demo_top_note}")

    output(f"  Requested melody note: {demo_melody_note}")

    if occurrences:

        matches = ", ".join(
            f"string {o.string_index} ({o.name})"
            for o in occurrences
        )

        output(f"  Melody match found on: {matches}")

        output(
            "  -> melody match != top note match:",
            f"{demo_melody_note} is NOT the top note ({demo_top_note}),",
            "but it IS genuinely present in this chord"
        )

    else:

        output("  No melody match found.")

    output("\n--- End Melody Occurrence Demo ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: melody realization diagnostic demo
    # ---------------------------------------------------------
    #
    # Shows the real My Favorite Things example (Cmaj7, melody
    # B3, aEADE tuning) through diagnose_melody_realization().
    # Purely diagnostic -- does not change any recommendation or
    # substitution behavior. Not connected to scoring or the
    # report. Safe to delete this block once it's no longer
    # needed.

    output("--- Melody Realization Diagnostic Demo (temporary) ---")

    a_modal_sawmill = get_tunings()["A Modal Sawmill"]  # aEADE

    cmaj7_service = ChordService(ChordLibrary())

    cmaj7_shapes = cmaj7_service.get_shapes(
        a_modal_sawmill, "C", 0, "maj7", "Maj 7"
    )

    diagnostic = diagnose_melody_realization(
        a_modal_sawmill, "C", 0, "maj7", "B3", cmaj7_shapes
    )

    output("\nCmaj7, melody B3 (aEADE):")

    output(
        "  Theoretical chord-tone match:",
        "YES" if diagnostic.category != "NOT_A_CHORD_TONE" else "NO"
    )

    output(
        "  Usable banjo voicing containing B3:",
        "YES" if diagnostic.matches else "NO"
    )

    if diagnostic.matches:

        for match in diagnostic.matches:

            output(
                f"    {match.shape} [{match.source}]:",
                f"string {match.string_index}, fret {match.fret},",
                f"pitch {match.sounding_note}",
                f"(voicing quality: {match.voicing_quality_category})"
            )

    output("\n--- End Melody Realization Diagnostic Demo ---\n")

    # ---------------------------------------------------------
    # TEMPORARY: FretDiagram ground-truth demo
    # ---------------------------------------------------------
    #
    # Shows real chord-symbol + actual-fingering pairs read
    # straight from a score's own <FretDiagram> data (via
    # Harmony.shape, populated by read_harmonies() -- see
    # parser.py). This is ground truth for what was actually
    # played, separate from any generated/ranked recommendation.
    # Not connected to scoring, chord generation, or any
    # recommendation logic. Safe to delete this block once it's
    # no longer needed.
    #
    # Note: Harmony only tracks which MEASURE a chord falls in,
    # not its beat position (see read_harmonies()'s own
    # docstring) -- so melody_note_for_harmony()'s answer is a
    # measure-level approximation, and no beat number is shown
    # below, since the parser doesn't actually have one to report.

    my_favorite_things_path = (
        PROJECT_FOLDER / "My_Favorite_Things__Em__aEADE__.mscz"
    )

    if my_favorite_things_path.exists():

        output("--- FretDiagram Ground Truth Demo (temporary) ---")

        mft = MuseScoreFile(my_favorite_things_path)

        mft.open()
        mft.read_time_signature()
        mft.read_melody_notes()
        mft.read_harmonies(4)

        output(
            f"\n{'Measure':<10}{'Beat':<7}{'Chord':<8}"
            f"{'Shape':<8}Melody"
        )

        # The specific examples from the investigation -- not a
        # dump of all 62 harmonies with a shape, which would be
        # exactly the excessive diagnostic output this project has
        # deliberately avoided everywhere else.
        highlighted_measures = {31, 38, 49, 59, 72}

        for harmony in mft.score.harmonies:

            if not harmony.shape:

                continue

            if harmony.measure not in highlighted_measures:

                continue

            melody_midi = mft.score.melody_note_for_harmony(harmony)

            melody_name = (
                midi_to_note_name(melody_midi)
                if melody_midi is not None
                else "?"
            )

            # Beats are tracked 0-indexed internally (0.0 = the
            # downbeat); +1 here just for the musician-facing
            # display convention ("beat 1", not "beat 0").
            beat_display = harmony.beat + 1

            output(
                f"{harmony.measure:<10}{beat_display:<7.1f}"
                f"{harmony.symbol:<8}{harmony.shape:<8}"
                f"{melody_name}"
            )

        output("\n--- End FretDiagram Ground Truth Demo ---\n")

    else:

        output(
            "\n(FretDiagram ground truth demo skipped -- "
            f"{my_favorite_things_path.name} not found.)"
        )

    # ---------------------------------------------------------
    # TEMPORARY: shape selection demo
    # ---------------------------------------------------------
    #
    # Shows select_shape_for_melody() picking a single best
    # shape and honestly labeling how well it realizes the
    # melody -- direct (lead voice), indirect (present, but not
    # the lead voice), or not at all. Uses the real My Favorite
    # Things Cmaj7/B3/aEADE case alongside a deliberately
    # impossible one (melody not even a chord tone), so the
    # difference is visible side by side. Not connected to
    # scoring, the report, or tuning recommendations.

    output("--- Shape Selection Demo (temporary) ---")

    chord_service_for_selection = ChordService(ChordLibrary())

    a_modal_sawmill_for_selection = get_tunings()["A Modal Sawmill"]

    for label, tuning, root, root_pc, code, display, melody in [
        (
            "C Major/Open G, melody E",
            get_tunings()["Open G"], "C", 0, "", "Major", "E"
        ),
        (
            "Cmaj7/aEADE, melody B3 (real arrangement case)",
            a_modal_sawmill_for_selection,
            "C", 0, "maj7", "Maj 7", "B3"
        ),
        (
            "Cmaj7/aEADE, melody D (not a chord tone)",
            a_modal_sawmill_for_selection,
            "C", 0, "maj7", "Maj 7", "D"
        ),
    ]:

        result = chord_service_for_selection.select_shape_for_melody(
            tuning, root, root_pc, code, display, melody
        )

        output(f"\n{label}:")

        selected = (
            result.selected_shape.shape
            if result.selected_shape
            else "(none)"
        )

        output(f"  Selected shape: {selected}")

        output(f"  Realization tier: {result.realization_tier}")

        output(f"  Diagnosis: {result.diagnosis.category}")

    output("\n--- End Shape Selection Demo ---\n")

    # ---------------------------------------------------------
