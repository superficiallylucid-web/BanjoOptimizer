# PROJECT_VISION.md

# Banjo Optimizer / Banjo Navigator

*Working Vision Document*

---

## Purpose

Banjo Optimizer helps a banjo player choose the best setup for a song.

Rather than simply ranking tunings, the software analyzes a MuseScore file, recommends several excellent setups, explains why they were chosen, and helps the musician decide which one best fits their playing style and performance goals.

Over time, the project will evolve into **Banjo Navigator**: a musical notebook that remembers arrangements, performance decisions, and player preferences.

---

# Philosophy

There is rarely one "correct" tuning.

Instead, there are trade-offs between:

* Melody
* Chord accompaniment
* Chords and melody together
* Playability
* Familiarity
* Performance practicality

The software should help the musician understand these trade-offs rather than simply choosing one answer.

The musician always makes the final decision.

---

# Current Workflow

MuseScore Score

↓

Analyze Music

↓

Recommend Setups

↓

Player Experiments

↓

Player Chooses

↓

Decision Stored for Future Use

---

# Core Concepts

## Song

A MuseScore score being analyzed.

---

## Setup

A setup consists of:

* Base tuning
* Capo position
* Fifth-string tuning
* Sounding tuning

Example:

Base tuning: gDGBD

Capo: 3

5th string: f

Sounding tuning: fFB♭DF

The setup—not just the tuning—is what the player actually uses.

---

## Recommendation

The optimizer normally presents only the top three recommended setups.

Each recommendation explains *why* it was selected.

Large ranking tables are reserved for the Deeper Dive report.

---

## Deeper Dive

A detailed report containing information useful for analysis but not normally needed during performance.

Examples:

* Complete tuning rankings
* Historical tunings
* Key confidence
* Scoring details
* Debug information
* Future algorithm explanations

---

## Musical Notebook

Long-term vision:

Remember previous decisions for every song.

Examples:

* Selected setup
* Other setups tried
* Why they were rejected
* Performance notes
* Last performed
* User comments

The notebook should become the player's musical memory.

---

# Design Principles

* Less output is better.
* Show only information that helps the musician make a decision.
* Explain recommendations.
* Separate player information from debugging information.
* Keep the interface calm and uncluttered.
* Preserve the reasoning behind every recommendation.
* Remember previous decisions.
* Build features that reduce preparation time before performances.

---

# Current Optimization Ideas

Current heuristics include:

* Key compatibility
* Open chord tones
* Fifth-string usefulness
* Melody transitions
* Average fret position
* Common tuning bonus

Potential additions:

* Lowest melody note accessibility
* Lowest melodic range accessibility
* Phrase consistency
* Left-hand movement
* Chord difficulty
* Chord transition difficulty

---

# Future Optimization Goals

The user should eventually be able to choose the optimization goal before analysis.

Examples:

### Melody

Optimize for comfortable melody playing.

### Chords + Melody

Optimize for solo banjo arrangements where melody and harmony are both important.

### Chord Accompaniment

Optimize for accompanying singing or other musicians.

Changing the goal should change the weighting of the scoring algorithm rather than the algorithm itself.

---

# Performance Assistant

Future capability.

Given multiple songs, recommend a performance order that minimizes:

* Retuning
* Capo changes
* Fifth-string adjustments

The goal is smoother live performances.

---

# MuseScore Integration

Future priority.

Export recommended setups directly into MuseScore so the player can quickly test:

* Tablature
* Fingerings
* Chords
* Melody

Rapid experimentation is more valuable than attempting to predict the perfect arrangement.

---

# User Feedback

The software should eventually learn from the player's choices.

Possible feedback includes:

* Which setup was ultimately chosen
* Melody rating
* Chord rating
* Overall playability
* Performance notes

The software should assist decision-making, not replace it.

---

# Completed Milestones

* Modular project structure
* MuseScore parser
* Key estimation
* Tuning optimizer
* Executable build
* Logging
* Cleaner user output
* Top three recommendations
* Recommendation explanations
* Separation of player report and Deeper Dive foundation

---

# Open Questions

* How should setup data be represented internally?
* What is the best format for storing the player's notebook?
* How should MuseScore export be implemented?
* How should player feedback influence future recommendations?
* When should the project officially become "Banjo Navigator"?

---

# Long-Term Vision

The project is evolving beyond a tuning optimizer.

The long-term goal is to create a trusted musical assistant that helps banjo players:

* discover arrangements,
* compare alternatives,
* make informed musical decisions,
* prepare performances,
* and remember those decisions for years to come.

The software should feel less like an optimizer and more like an experienced musical partner.
