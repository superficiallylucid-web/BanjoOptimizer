# Changelog

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
