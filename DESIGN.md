# Banjo Optimizer — Playing Model Design

## Core concept

A chord is not an isolated event. It establishes a physical hand position, and
the melody notes around it are easier or harder to play depending on that
position. The Playing Model evaluates melody and chords together, not as two
independent systems:

```
tuning → chord shapes → melody locations → chord/melody combinations
       → phrase evaluation → tuning score
```

Implemented in `playing_model.py`, reusing existing machinery throughout
(`chord_service.py` for candidate shapes, `fretboard.py` for realizations and
shape geometry, `melody_box_analysis.py` for the melody passage around each
chord). No music theory or fretboard math is duplicated.

## Chord-shape playability (intrinsic, independent of melody)

Each candidate chord shape gets a playability score from:

- **Finger load** — fewer fretted fingers is better (frees fingers for
  melody); a 4-finger chord takes a real penalty.
- **Finger geometry** — the hand approaches the neck at an angle, so frets
  that rise (or stay level) moving from string 4 toward string 1 are
  rewarded; frets that fall are penalized. `1234` scores well; `4321` does
  not, even though both use the same four fingers and the same span.
- **Fret span** — a span up to 3 frets costs nothing; beyond that, each extra
  fret adds a penalty. `2004` (span 2, only 2 fingers) scores far better than
  `3206` (span 4, awkward finger geometry), matching the intended contrast
  even though `2004`'s raw span isn't trivially small.
- **Open strings** — string 1 and string 4 open are worth more than string 2
  or 3 open, matching general banjo-hand ergonomics.

These are documented as *initial heuristics, not immutable rules* — simple,
named, small in number, verified against the specific worked examples above,
not against exhaustive real-world calibration.

## Melody note locations

Every melody note's realizations are found via the existing
`fretboard.find_positions()` — every string/fret option, not a single
pre-assigned "best" string. Open strings (fret 0) are valid realizations.

## Combining a chord shape with melody locations

For each melody note against each candidate chord shape:

- **Contained in the chord** — the melody pitch already sounds in the shape:
  the strongest bonus.
- **Free finger** — an unused string, within the chord's own four-fret
  working position: a genuine but smaller bonus.
- **String accessibility** — a physical preference (string 1 easiest, string
  4 hardest), applied as a small additive bonus, never a hard filter.
- **Proximity** — realizations near the chord's own fret position are
  favored, but a melody note is never required to share a string with a
  chord note.

## Phrase window and continuity

A chord shape is evaluated against a small window: the last two notes of the
*previous* melody segment (lead-in) through every note up to the *next*
chord symbol (matches `melody_box_analysis.py`'s existing box definition —
a box is only ever bounded by real chord symbols). This is not an
instantaneous event at the chord symbol's exact beat.

Between consecutive chosen shapes, a modest continuity bonus favors small
hand-position movement — but the penalty is capped rather than growing
without bound, so a genuinely better up-the-neck solution is never
automatically rejected for requiring a bigger jump.

## Chordless passages

Handled naturally by the box model itself: a box only ever ends at a real
chord symbol, so several measures with no chord symbol simply become one
long box, analyzed the same way as any other. No separate mechanism was
needed for this.

## 5th string

Considered separately from the fretted melody/chord fingering — a bonus when
a melody note's pitch class matches the 5th string's fixed open pitch,
independent of any fretted realization.

## Canonical example: E5 → A5 → C4 → Bsus4 (My Favorite Things, aEADE)

This sequence is the model's working test case. `E5` (`0220`) is chosen not
just because it's playable, but because it's already prepared by the B
lead-in, keeps E available at the chord's own onset, and leaves B and a free
5th-string opportunity available afterward — evaluated directly in
`tests/test_playing_model.py` and confirmed against real data.

## Integration status — read before extending this further

**This model is not wired into `optimizer.py`'s tuning score.**
`TuningAnalyzer` now accepts an optional `harmonies` parameter
(`TuningAnalyzer(notes, key, harmonies)`, defaulting to `[]` — every existing
two-argument call site is unaffected) so the Playing Model has real
chord/harmony context to integrate against once that step happens.
`score_tuning()` does not read `self.harmonies` yet; supplying it has no
effect on the current score. `main.py` now calls `read_harmonies()` on the
melody staff and passes the result through.

The model produces real, structured phrase- and tuning-level scores
(`TuningPlayingModelResult`), exposed as a diagnostic (`dev_demos.py`) rather
than blended into production ranking. **Recommended next step:** integrate
this model's tuning-level score into `score_tuning()` as an explicit, small,
additive term, using the harmony context now available on the analyzer —
once its weights have been checked against more real scores than this first
pass covered.
