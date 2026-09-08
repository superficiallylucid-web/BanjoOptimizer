# Production Code Sync — Delivery Manifest

## What this is

21 files: every production `.py` module at the project root, plus
`main.py` itself. This is a **full replacement** of your current
copies with what's been running in this sandbox throughout the whole
BO-149 effort — which, per your own confirmation, includes BO-142
through BO-148.6 development that predates this session and was
never synced to your local checkout.

This is a bigger, higher-stakes change than any of the test-file
work so far. These are the files that decide actual chord shapes,
fret positions, and melody/chord selection — not paths or fixtures.
Please treat this delivery with more caution than the test-file
packages.

## Files in this package (21)

```
chord_generator.py
chord_library.py
chord_service.py
chord_vocabulary_analysis.py
dev_demos.py
fretboard.py
hand_position.py
main.py
melody_box_analysis.py
models.py
music.py
optimizer.py
output.py
parser.py
playability.py
playing_model.py
recommendations.py
score_generator.py
shape_ratings.py
stroke_cycle.py
tunings.py
```

This list was built by tracing the complete transitive import graph
from `main.py` and from every module `main.py` or another production
module imports (confirmed directly, not assumed) -- including two
real dependencies that are easy to miss from the top level:
`shape_ratings.py` (imported by `playability.py`) and `dev_demos.py`
(imported by `main.py` itself).

## What is deliberately NOT in this package

- Anything in `tests/` — separate, already delivered.
- `bo59_hp_tracer.py`, `bo60_scenario_scanner.py`,
  `populate_template.py`, `populate_template_treble_only.py` —
  confirmed these are not imported by `main.py` or any production
  module. They look like standalone dev/investigation scripts from
  past work, not things the running application depends on. If any
  of these turn out to matter to you for a reason I can't see from
  here, say so and I'll re-check.
- The stale root-level `test_*.py` duplicates I flagged earlier in
  this session (`test_bo103_initial_hand_position.py` and similar,
  sitting at the project root instead of `tests/`) — untouched,
  unrelated to this delivery.

## Before you apply this

**Back up your current 21 files first**, or apply this on a branch,
so you can diff against your own history and revert cleanly if
needed. This is real behavior change, not a mechanical path fix --
worth being able to see exactly what moved.

## After you apply this

1. Copy all 21 files over your project root, replacing your current
   copies exactly.
2. Re-run the full suite you've been using to track this
   (`pytest tests/ ...`) and compare against the 74-failure result
   that prompted this delivery.
3. Expect a real drop in failures -- the five tests whose tracebacks
   triggered this (`test_bo30_bidirectional_anchor`,
   `test_bo35_fd_position_consistency`,
   `test_bo37_preceding_fd_inclusion`, and two in
   `test_tab_from_template.py`) should now match this sandbox's
   values, since the assertions were written against this exact
   code. I can't promise every one of the 74 resolves this way --
   some failures in that list were already independently traced to
   fixture-content issues (Aureolin/MFT) or genuinely unavailable
   fixtures (BO-125/BO-53), and this delivery doesn't touch either
   of those.
4. If new, different failures appear after this that weren't in the
   original 74, that's worth flagging distinctly -- it would mean
   something about how these files interact with your specific
   local environment differs from mine in a way neither of us has
   seen yet.
