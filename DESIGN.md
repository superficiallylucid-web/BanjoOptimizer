# Banjo Optimizer Design Document

## Overview

Banjo Optimizer is a Python application designed to analyze MuseScore banjo arrangements and recommend practical banjo tunings and fingering approaches.

The goal is not simply to find a mathematically possible tuning. The goal is to help a banjo player find an arrangement that is musically practical, playable, and understandable.

The optimizer should eventually be able to explain its recommendations in terms a musician can understand:

* why a tuning was selected,
* what musical advantages it provides,
* where compromises exist,
* and how the recommended approach affects playing.

---

# Current Architecture

The project is organized into several modules with separate responsibilities.

## main.py

Application entry point.

Responsibilities:

* Locate MuseScore files.
* Manage application folders.
* Run score analysis.
* Generate output reports.
* Coordinate parser and optimizer components.

The program supports both:

* normal Python execution,
* packaged executable execution through PyInstaller.

---

## parser.py

MuseScore file parsing.

Responsibilities:

* Open `.mscz` files.
* Extract XML information.
* Read score metadata.
* Extract notes from the selected melody staff.

Current behavior:

* Melody extraction currently assumes Staff 4 contains the melody.
* Defensive checks exist to prevent empty note analysis.

Future improvement:

* Detect the melody staff automatically instead of relying on a fixed staff number.

---

## score.py

Represents score information.

Responsibilities:

* Store extracted score data.
* Hold title, key, time signature, and notes.
* Provide a structured representation for analysis.

---

## music.py

Music theory utilities.

Responsibilities:

* MIDI note handling.
* Pitch classes.
* Key analysis.
* Scale and chord-related utilities.

This module should remain independent of banjo-specific logic where possible.

---

## tunings.py

Banjo tuning definitions.

Responsibilities:

* Store known banjo tunings.
* Provide tuning metadata.
* Describe string configurations.

Examples currently supported:

* Open G
* C Standard
* Double D
* G Modal Sawmill

---

## models.py

Shared data structures.

Responsibilities:

* Provide common objects used throughout the application.
* Reduce dependency between modules.
* Keep data representation consistent.

---

## optimizer.py

Core recommendation engine.

Responsibilities:

* Analyze a score against available tunings.
* Calculate suitability scores.
* Rank recommended setups.
* Generate explanations for recommendations.

Current scoring considers factors such as:

* key compatibility,
* open-string support,
* chord-tone support,
* fifth-string usefulness,
* general playability.

---

## output.py

Reporting utilities.

Responsibilities:

* Format program output.
* Write analysis results.
* Provide readable reports for musicians.

---

# Optimization Philosophy

The optimizer should not simply maximize a numerical score.

A good recommendation should represent a practical playing choice.

Important principles:

## Playability over mathematical perfection

A theoretically ideal tuning may not be the best recommendation if it creates awkward fingering or unnecessary complexity.

## Explainability

Every recommendation should eventually answer:

"Why is this tuning better?"

Examples:

* More open chord tones.
* Better use of the fifth string.
* Fewer large position changes.
* Better fit for the song's key.

## Balanced scoring

Each scoring component should contribute in a predictable way.

Scores should avoid:

* unlimited accumulation,
* song-length bias,
* one factor overwhelming all others.

Future scoring improvements should favor:

* normalized values,
* weighted categories,
* capped contributions where appropriate.

---

# Current Known Limitations

## Melody staff detection

The parser currently assumes Staff 4 contains the melody.

Future:

* Detect melody staff automatically.

## Fretboard modeling

The project currently focuses primarily on tuning analysis.

Future:

* Improve fret-position analysis.
* Favor practical playing positions.
* Avoid unnecessary movement.
* Consider phrase-level fingering decisions.

## Chord awareness

Future improvements:

* Incorporate chord symbols from MuseScore.
* Use chord information when evaluating tuning choices.
* Explain chord-tone advantages.

## User-facing output

Future improvements:

* Generate more detailed reports.
* Include explanations of tradeoffs.
* Potentially generate improved MuseScore files with annotations.

---

# Development Workflow

The GitHub repository is the source of truth for the project.

Important branches:

* `main` - stable/public version
* `redesign` - active development branch

Before major changes:

1. Make a focused change.
2. Test with real MuseScore files.
3. Commit the change.
4. Push to GitHub.

Small, understandable improvements are preferred over large rewrites.

---

# Current Test Files

The project uses MuseScore files for validation, including:

* White Christmas (G)
* My Favorite Things (Em)
* Cousin Sally Brown (D)

These files help verify:

* parsing,
* key detection,
* tuning recommendations,
* regression behavior.

---

# Current Status

Completed:

* MuseScore file parsing foundation.
* Music theory utilities.
* Banjo tuning database.
* Initial optimizer framework.
* Output reporting.
* PyInstaller executable packaging.
* Basic automated tests.
* Defensive handling for missing melody data.

Active development:

* Improving optimizer intelligence.
* Refining scoring methodology.
* Improving explanations.

Long-term goal:
Create a tool that helps banjo players discover practical, musical arrangements while understanding the reasoning behind each recommendation.
