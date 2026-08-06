# Banjo Optimizer Architecture

## Purpose

This document describes the overall architecture of Banjo Optimizer.

Its purpose is to explain how the system is organized, define the responsibility of each module, and provide guidance for future development. New features should fit into this architecture rather than changing it unnecessarily.

---

# Design Philosophy

Banjo Optimizer is intended to function like an experienced banjo player.

Rather than searching for a single "correct" answer, it should:

* analyze the music
* generate multiple reasonable alternatives
* evaluate those alternatives
* explain why each recommendation was made

Every recommendation should eventually be explainable to the user.

---

# High-Level Data Flow

```text
MuseScore Score
        │
        ▼
Parser
        │
        ▼
Musical Models
        │
        ▼
Optimizer
        │
        ▼
Chord Service
   ┌───────────────┐
   │               │
   ▼               ▼
Chord Library   Chord Generator
                     │
                     ▼
                 Fretboard
```

---

# Current Modules

## parser.py

Reads MuseScore files.

Responsibilities:

* Read notes
* Read harmony symbols
* Read score metadata

Should never:

* Recommend tunings
* Generate chord shapes

---

## music.py

Music theory utilities.

Responsibilities:

* Pitch classes
* Chord tones
* Keys
* Scales

Should contain no banjo-specific logic.

---

## models.py

Shared data structures used throughout the project.

Responsibilities:

* Dataclasses
* Shared object definitions

Should contain no business logic.

---

## optimizer.py

The musical decision engine.

Responsibilities:

* Analyze melody
* Evaluate tunings
* Score recommendations
* Produce tuning recommendations

Should not generate chord shapes directly.

---

## fretboard.py

Represents the banjo fretboard mathematically.

Responsibilities:

* Locate notes
* Locate pitch classes
* Fretboard calculations

Should not decide whether a chord is good.

---

## chord_generator.py

Generates possible chord shapes.

Responsibilities:

* Produce candidate chord shapes
* Return multiple alternatives

Should not determine which candidate is best.

---

## chord_library.py

Stores known chord shapes.

Responsibilities:

* Load verified chord shapes
* Return stored shapes

Should not generate new shapes.

---

## chord_service.py

Combines all chord information.

Responsibilities:

* Retrieve verified shapes
* Generate additional candidates
* Merge results
* Remove duplicates
* Return a unified list

This module is intended to become the central access point for chord selection.

---

# Planned Modules

## playability.py

Evaluates whether generated chord shapes are practical.

Responsibilities:

* Reject impossible shapes
* Score playability
* Explain decisions

---

# Future Enhancements

These features are expected to be added gradually:

* Melody-note matching
* Chord transition analysis
* User preference learning
* Comfort scoring
* Performance recommendations
* Alternative tunings
* Automatic explanation generation

Each should build upon the existing architecture rather than replacing it.

---

# Development Principles

1. Small incremental changes.

Each change should be independently testable.

2. Preserve existing behavior.

Whenever possible, new functionality should not change existing optimizer output.

3. Single responsibility.

Each module should have one clearly defined purpose.

4. Explainable recommendations.

Banjo Optimizer should eventually explain every recommendation it makes.

5. Verified knowledge over generated knowledge.

Verified chord shapes always take precedence over generated candidates.

6. Human feedback improves the system.

Generated knowledge may be promoted to verified knowledge after user validation.

---

# Long-Term Vision

The goal is not merely to analyze banjo music.

The goal is to become an intelligent musical assistant that helps players choose tunings, understand why those tunings work, evaluate chord options, and continually improve through experience while remaining transparent in its reasoning.
