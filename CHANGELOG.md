# Changelog

## 2026-08-02

### Fixed

* Reduced the influence of the key-fit bonus on tuning scores, so a tuning "sounding right" for the key no longer disproportionately outweighs actual playability.
* Fixed the hand-movement score to be normalized per note transition instead of summed raw across the whole song. The raw sum scaled with song length and could silently overpower every other scoring component, including key fit and open-string support.
* Capped the 5th-string transition-bridging score to prevent the same class of unnormalized-sum issue from affecting longer or leap-heavy songs.
* Replaced the hardcoded "melody is always on Staff 4" assumption with automatic melody-staff detection (`read_melody_notes()`), so files with a different staff layout are handled correctly instead of failing.

### Added

* Added chord symbol (Harmony) extraction from MuseScore files: a MuseScore TPC-to-note-name decoder and a chord-quality lookup table.
* Added automatic tuning identification from a file's embedded string data, rather than trusting the filename or title.

### Notes

* Verified the hand-movement fix against the White Christmas (G major) and Cousin Sally Brown (D major) test scores; both now recommend the musically expected tuning with a clear scoring margin instead of a near-tie.
* Confirmed filenames/titles cannot be trusted for tuning metadata — a test file named for one tuning was found to actually contain a different tuning in its embedded MuseScore data.

### Design Direction

* Chord-based playability scoring (using the newly extracted chord data) identified as the next major feature, deferred for now as a larger, separate piece of work.
* Established convention: always read tuning from embedded MuseScore data, never from filenames or titles.

---

## 2026-07-31

### Added

* Added defensive error handling when no melody notes are found on the expected MuseScore staff.
* Added project design documentation to preserve architecture decisions and development direction.

### Fixed

* Prevented the optimizer from continuing with empty note data when a MuseScore file does not contain notes on the expected melody staff.

### Notes

* Verified the change using the White Christmas (G) test score.
* Confirmed normal parsing, key detection, and tuning recommendation output after the update.

---

## 2026-07-30

### Changed

* Reduced user output to the top three recommendations.
* Removed historical tunings from the main report.
* Introduced the "Deeper Dive" concept.
* Defined "Setup" as:

  * Base tuning
  * Capo
  * 5th string
  * Sounding tuning

### Design Direction

* Identified Banjo Navigator as the long-term vision for the project.




## 2026-07-31

### Added

* Added defensive error handling when no melody notes are found on the expected MuseScore staff.
* Added project design documentation to preserve architecture decisions and development direction.

### Fixed

* Prevented the optimizer from continuing with empty note data when a MuseScore file does not contain notes on the expected melody staff.

### Notes

* Verified the change using the White Christmas (G) test score.
* Confirmed normal parsing, key detection, and tuning recommendation output after the update.

---

## 2026-07-30

### Changed

* Reduced user output to the top three recommendations.
* Removed historical tunings from the main report.
* Introduced the "Deeper Dive" concept.
* Defined "Setup" as:

  * Base tuning
  * Capo
  * 5th string
  * Sounding tuning

### Design Direction

* Identified Banjo Navigator as the long-term vision for the project.
