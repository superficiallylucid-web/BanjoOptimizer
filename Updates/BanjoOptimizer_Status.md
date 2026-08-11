# Banjo Optimizer --- Project Status

**Status date:** 2026-08-11\
**Project:** Banjo Optimizer v1.0\
**Purpose:** Analyze MuseScore `.mscz` scores and recommend practical
banjo tunings, with chord-shape and melody-placement analysis becoming
increasingly important.

------------------------------------------------------------------------

## 1. Current Project Direction

The project has moved beyond simply scoring tunings.

The current architectural direction is:

1.  Parse the MuseScore score accurately.
2.  Understand the musical context:
    -   key
    -   melody
    -   harmony/chord symbols
    -   timing/measure/beat
    -   actual banjo chord shapes when available
3.  Generate candidate banjo chord shapes.
4.  Evaluate playability and voicing quality.
5.  Determine whether a melody note can actually be realized in a usable
    chord shape.
6.  Eventually use that information to support intelligent chord
    substitutions.
7.  Later, allow the user to suggest a tuning and compare it directly
    with BO's recommendations.

**Important principle:** Do not jump into chord-substitution logic until
melody-aware chord-shape analysis is reliable.

------------------------------------------------------------------------

## 2. User Preferences for Working With Claude

The user wants **one Claude instruction set at a time**.

Claude has repeatedly timed out/locked out during large tasks. Even with
Claude Pro, prefer tasks that are:

-   narrowly scoped
-   independently testable
-   finishable in one session
-   followed by a concise final report

Do not give Claude multiple unrelated tasks in one request.

The user archives each completed Claude task in Git.

Preferred commit naming convention:

`BO-## ShortDescription`

Examples:

-   `BO-01 Baseline`
-   `BO-02 ChordVoicingSuitability`
-   `BO-03 MelodyRealizationDiagnostic`

The user wants the sequence number to make it easy to track:

**Claude instruction → implementation → download/deploy → Git commit**

------------------------------------------------------------------------

## 3. Important Real-World Test Scores

### My Favorite Things

-   Key: E minor
-   Time signature: 3/4
-   Total notes: 184
-   Current recommended tunings:
    1.  A Modal Sawmill (`aEADE`)
    2.  Old G (`gDGDE`)
    3.  Double D (`aDADE`)

Important real-world chord examples:

  --------------------------------------------------------------------------
  Measure        Original       Banjo chord    Actual         Melody
                 harmony                       FretDiagram    
  -------------- -------------- -------------- -------------- --------------
  m1 beat 2      Cmaj7          E5             `0220`         E4

  m5 beat 2      Em             E5             `0220`         B3

  m9 beat 2      Em             Em             `0220`         B3

  m31 beat 2     Cmaj7          Em             `0220`         B3

  m38 beat 1     Ebdim          B7             `2314`         D#4

  m49 beat 2     Cmaj7          Em             `0220`         B3

  m59 beat 1     Ebdim          A7             `3425`         A4

  m68 beat 1     A              Asus4          `0000`         A3

  m72 beat 1     D6             Em             `0223`         B3
  --------------------------------------------------------------------------

**Critical observation:** the same chord symbol can use different actual
shapes.

For example:

-   `Em` at m9/m31/m49 uses `0220`
-   `Em` at m72 uses `0223`

Therefore:

> A chord symbol does NOT tell us which fingering/shape is actually
> being played.

This matters for future parsing and validation.

------------------------------------------------------------------------

## 4. FretDiagram Parsing

MuseScore uses the XML tag:

`<FretDiagram>`

Not `<FretboardDiagram>`.

The current project has confirmed that actual diagrams encode each
string separately.

Example:

``` xml
<string no="0"><marker>circle</marker></string>
<string no="1"><dot fret="2"/></string>
<string no="2"><dot fret="2"/></string>
<string no="3"><marker>circle</marker></string>
```

This decodes to:

`0220`

The project previously confirmed that the parser did **not** originally
read FretDiagram data.

A future parser change can attach the actual shape to the corresponding
`Harmony`, but this was deliberately kept separate from the earlier
diagnostic work.

------------------------------------------------------------------------

## 5. Chord-Shape / Voicing Quality Work Already Completed

Claude implemented a voicing-quality classification in `music.py`.

New conceptual categories:

-   `ROOT_PRESENT`
-   `ROOTLESS_STRONG`
-   `ROOTLESS_WEAK`

The classifier:

`music.classify_voicing_quality(root_pc, quality_code, sounding_pitch_classes)`

is derived structurally from existing chord-quality interval data rather
than hardcoding individual chords.

The concept is:

-   Root present → strongest category.
-   Rootless but all defining tones present → strong.
-   Rootless and missing defining tones → weak.

The score differentiates candidates within a category.

Important: **rootless shapes are not rejected outright.**

This was intentional because rootless voicings can be musically useful,
especially in dominant-7th contexts.

### Cmaj7 / aEADE example

The generated candidates included:

-   `0220`
-   `0250`

Both place the desired B3 on the 3rd string, 2nd fret.

However, these are rootless shapes.

Theo's Cmaj7 diagrams for aEADE occupy approximately frets 5--11 and do
not explore the low/open region.

This established an important distinction:

> "Mathematically playable" is not the same thing as "a shape a player
> would actually choose."

------------------------------------------------------------------------

## 6. Melody Realization Diagnostic

Claude added:

`chord_service.diagnose_melody_realization(...)`

with three categories:

-   `CHORD_TONE_AND_USABLE_VOICING`
-   `CHORD_TONE_BUT_NO_USABLE_VOICING`
-   `NOT_A_CHORD_TONE`

This separates:

1.  The melody note is not part of the chord.
2.  The melody note is theoretically part of the chord, but no usable
    candidate shape realizes it.
3.  A usable chord shape actually contains the melody note.

The diagnostic records actual string/fret information for melody
occurrences.

The full test suite reached:

**47/47 passing**

at the completion of that task.

------------------------------------------------------------------------

## 7. Important Correction About the Original Cmaj7/B Example

The original reasoning evolved.

The user initially described a Cmaj7/B3 problem in aEADE.

Current investigation established:

-   Cmaj7 contains B, theoretically.
-   Current BO generated low-position shapes such as `0220` and `0250`
    can contain B3.
-   Theo's Cmaj7 diagrams do not include the low/open position.
-   The actual arrangement uses `0220` in several places.

However, one must not incorrectly combine facts from different musical
locations.

The exact score data show:

-   m1: Cmaj7 + E5 + `0220` + melody E4
-   m5: Em + E5 + `0220` + melody B3
-   m49: Cmaj7 + Em + `0220` + melody B3

The user also moved some chord events in the arrangement.

Therefore, future test cases should preferably use examples where:

-   the chord/harmony event
-   the melody note
-   and the actual shape

are tied to the **same musical moment**.

Do not assume that a chord symbol and a shape from adjacent events
belong to the same event.

------------------------------------------------------------------------

## 8. Chord Symbol vs Actual Shape

This is a central architectural lesson.

A chord symbol describes harmonic intent.

A FretDiagram describes the actual fingering chosen by the
arranger/player.

The same chord symbol can correspond to different shapes in the same
score.

Therefore:

-   `Harmony` should not be treated as equivalent to `FretDiagram`.
-   Future analysis should keep harmonic identity and physical
    realization as separate concepts.
-   If a FretDiagram is available, it is valuable ground-truth evidence
    about what the arranger actually chose.

------------------------------------------------------------------------

## 9. Melody Matching Work

A known weakness was found in:

`ChordService.get_shapes_for_melody()`

The old implementation matched melody only against `top_note`.

That is incorrect for cases where the melody note occurs on an inner
string.

Example from the project:

Open-G G-major shape:

`0000`

Sounding notes:

-   D3
-   G3
-   B3
-   D4

The top note is D4, but B3 is genuinely present on the 2nd string.

Therefore:

> melody match ≠ top-note match

Claude began upgrading `get_shapes_for_melody()` to use:

`find_melody_occurrences()`

instead of only checking `top_note`.

This is the **current unfinished task**.

------------------------------------------------------------------------

## 10. Current In-Progress Task

Claude's latest task:

### Upgrade `get_shapes_for_melody()`

Goal:

Replace top-note-only matching with actual pitch occurrence matching.

Desired behavior:

-   A shape matches the melody if the requested melody pitch is actually
    sounding anywhere in the shape.
-   It should no longer require the melody to be the top note.

Claude had already:

-   inspected the current implementation
-   replaced the top-note matching logic
-   imported `find_melody_occurrences`
-   discovered that older tests used unrealistic fixtures with
    `tuning=None`
-   begun redesigning those fixtures using real tuning/shape data
-   reached the point where it was computing genuine fixtures rather
    than guessing

The task is **not finished yet**.

When continuing, instruct Claude to:

1.  Finish the fixture correction.
2.  Finish tests for the new behavior.
3.  Run the full regression suite.
4.  Verify both My Favorite Things and White Christmas.
5.  Report exact files changed and test counts.
6.  Do not expand scope.

------------------------------------------------------------------------

## 11. Do Not Do Yet

Do not currently ask Claude to:

-   implement chord substitution
-   redesign the tuning optimizer
-   redesign the scoring model
-   add FretDiagram parsing
-   clean up all temporary demos
-   add user-suggested tuning comparison
-   add transition/voice-leading analysis

Those are future tasks.

The current priority is to make melody-aware chord-shape selection
correct and tested.

------------------------------------------------------------------------

## 12. Future Feature: User-Suggested Tuning

A desired future feature is:

> Let the user suggest a tuning, then show that tuning alongside BO's
> recommendations so the user can see how it measures against them.

This should eventually be implemented as a comparison feature, not by
pretending the user-suggested tuning is one of BO's recommendations.

Likely future output:

-   BO recommendations
-   User-suggested tuning
-   comparative score/reasons
-   possibly ranking/position relative to BO's recommendations

Do not implement this until the current melody/chord-shape foundation is
stable.

------------------------------------------------------------------------

## 13. Temporary Demo Output

`main.py` currently contains numerous temporary demonstration blocks
covering:

-   chord library
-   chord library statistics
-   chord generator
-   inversion/top note
-   playability
-   chord service
-   melody/chord shape
-   melody occurrence
-   melody realization diagnostic

This is intentionally deferred cleanup.

Once the architecture stabilizes, these demos should eventually be
reorganized or removed rather than continuing to accumulate.

------------------------------------------------------------------------

## 14. Regression Baseline

At the completion of the melody realization diagnostic task:

-   Full test suite: **47/47 passing**
-   White Christmas recommendations unchanged
-   My Favorite Things runs cleanly
-   Existing tuning recommendation behavior remained unchanged

Earlier voicing-quality work had reached:

-   **42/42 passing**

before the melody realization diagnostic was added.

The exact current count should always be verified rather than assumed
after further changes.

------------------------------------------------------------------------

## 15. Working Philosophy

The project should favor:

-   real score evidence over invented examples
-   explicit separation of harmonic intent vs physical realization
-   melody-aware shape selection
-   practical playability over purely mathematical validity
-   explainable recommendations
-   conservative changes
-   regression testing after each architectural change
-   small, finishable Claude tasks

The most important recurring lesson is:

> The goal is not merely to find a chord that is theoretically correct.
> The goal is to find a chord shape that a banjo player can
> realistically use at the specific musical moment.

------------------------------------------------------------------------

## 16. Immediate Next Step

**Finish the current `get_shapes_for_melody()` upgrade.**

Do not begin another feature until that task is complete and the
regression suite is clean.

After that, reassess the architecture before selecting the next task.
