"""
gui.py

BO-152/153 -- the first, very-basic GUI (per BO-152's own phased
plan: "Very basic dialog: Pick .mscz, choose tuning/options, Run,
see basic result"). Calls main.run_optimizer() directly -- no
subprocess, no CLI simulation, matching the ideal architecture
BO-152's own request diagram called for (GUI and CLI both sitting
on top of the same application pipeline, not the GUI faking a
command-line invocation).

Two deliberate scope decisions for this first pass, agreed before
writing this file:

1. No "Generate TAB" / "Generate fretboard diagrams" checkboxes
   (present in BO-152's own mockup). Neither corresponds to a real
   toggle in run_optimizer() today -- TAB generation is always on,
   and fretboard diagrams are embedded in that TAB output, not a
   separate one. Showing checkboxes that don't do anything would
   be worse than omitting them; wiring real ones is future work
   this file doesn't attempt.
2. No output-location picker. run_optimizer() always writes to the
   application's own real output/ folder (project_folder's own
   "output" subdirectory) -- same as the CLI always has. A real,
   working picker needs run_optimizer() extended with a dedicated
   parameter first; out of scope here.

The "Tuning:" dropdown lists every named tuning in the catalog.
Selecting one resolves its underlying open-tuning symbol
internally (self._resolved_base_symbol -- never a second, visible
dropdown; BO-165 originally had one, "Capo tuning", removed in
BO-166 once investigation confirmed it was always a strict subset
of this combo's own list and added no real capability). For a
capo-derived tuning (Double D: base gCGCD, capo 2, 5th string A --
and, generalized in BO-166 using the exact same mechanism, A Minor,
A Modal Sawmill, and Open A), Capo and 5th string auto-populate
from that tuning's own real base_tuning/capo/fifth_string_note
metadata, reusing it directly rather than a second, separately-
maintained mapping -- and remain freely editable afterward, same
as for any other tuning.

No progress/status callback: run_optimizer() is called
synchronously, and the window will appear to hang for however long
optimization takes (confirmed in testing: a few seconds for a
single score). This is the same known limitation flagged in
run_optimizer()'s own docstring -- sys.stdout is redirected inside
that function, so this GUI cannot safely run it on a background
thread without that being addressed first. Fine for a first,
very-basic dialog; a real progress area is future work.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QComboBox, QSpinBox, QTextEdit, QFileDialog,
    QMessageBox, QGroupBox, QDialog
)
from PySide6.QtCore import Qt

import main
from tunings import get_tunings

# BO-160 -- was Path(__file__).parent, a separate, non-frozen-
# aware resolution from main.py's own (confirmed directly: this
# never checked sys.frozen at all). Fixed while adding settings-
# aware folder resolution anyway, since the two belong together.
PROJECT_FOLDER = main.resolve_project_folder()


def _default_scores_folder():
    # BO-160 -- re-reads settings on every call (not a cached
    # module-level constant, unlike before) so a change made via
    # the Settings dialog below takes effect immediately on the
    # next Browse click, without needing the app restarted.
    settings = main.load_settings(PROJECT_FOLDER)
    saved = settings.get("scores_folder")
    return Path(saved) if saved else PROJECT_FOLDER / "scores"


class BanjoOptimizerWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Banjo Optimizer")
        self.setMinimumWidth(520)

        self.selected_score_path = None

        layout = QVBoxLayout(self)

        # --- Input Score ---------------------------------------
        score_group = QGroupBox("Input Score")
        score_layout = QHBoxLayout(score_group)

        self.score_line_edit = QLineEdit()
        self.score_line_edit.setReadOnly(True)
        self.score_line_edit.setPlaceholderText(
            "No score selected"
        )

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse_clicked)

        score_layout.addWidget(self.score_line_edit)
        score_layout.addWidget(browse_button)

        layout.addWidget(score_group)

        # --- Tuning ----------------------------------------------
        # BO-157 -- "Number of tunings" replaces the former "Show
        # alternative tunings" checkbox + count entirely, per
        # explicit instruction. This is a genuinely different
        # mechanism from the old one, not just a relabel: it
        # controls run_optimizer()'s own num_tunings parameter
        # (BO-157), which returns exactly that many top-ranked
        # tunings unconditionally, straight off the ranked list --
        # unlike the old alternatives mechanism, there's no
        # separate "does rank 4+ still qualify as strong" test.
        # This GUI no longer calls alternatives at all (still
        # available to CLI callers via --alternatives, untouched).
        # Only meaningful under "Recommended Tuning" -- disabled
        # under "Use specific tuning", which always produces
        # exactly one result regardless.
        tuning_group = QGroupBox("Tuning")
        tuning_layout = QGridLayout(tuning_group)

        self.recommend_radio = QRadioButton("Recommended Tuning")
        self.recommend_radio.setChecked(True)

        # 11 is the real, total number of "modern" tunings the
        # recommender ranks (confirmed directly) -- asking for
        # more would just pad the list with weaker matches for no
        # benefit, so that's the genuinely meaningful cap here.
        self.num_tunings_spin = QSpinBox()
        self.num_tunings_spin.setMinimum(1)
        self.num_tunings_spin.setMaximum(11)
        self.num_tunings_spin.setValue(1)

        self.recommend_radio.toggled.connect(
            self.num_tunings_spin.setEnabled
        )

        self.specific_radio = QRadioButton("Use specific tuning")

        tuning_button_group = QButtonGroup(self)
        tuning_button_group.addButton(self.recommend_radio)
        tuning_button_group.addButton(self.specific_radio)

        # BO-165 -- "User-specific tuning" now lists all 13
        # built-in tunings (Double D included), matching what's
        # available to the recommender. This is the sole source of
        # truth for the underlying base tuning: selecting an entry
        # here decomposes it into its own base/capo/5th-string
        # (stored internally -- see self._resolved_base_symbol
        # below) via _sync_from_named_tuning(), reusing each
        # Tuning's own real base_tuning/capo/fifth_string_note
        # metadata rather than a second, separately-maintained
        # mapping. Double D, for example, resolves to base gCGCD,
        # Capo=2, 5th string=A -- its own real decomposition,
        # confirmed directly against tunings.py's own Double D
        # entry.
        #
        # BO-166 -- the former separate "Capo tuning" dropdown
        # (BO-165) is gone: it was always a strict subset of this
        # combo's own list (every entry it could ever show was
        # already directly selectable here), so it added no real
        # capability -- confirmed during BO-166's own investigation
        # -- and its resolved base is now purely internal state
        # (self._resolved_base_symbol) rather than a second visible
        # selector. Defaults to Open G (gDGBD), matching this
        # explicit selection below.
        all_tuning_label = QLabel("Tuning:")
        self.all_tunings_combo = QComboBox()
        for name in sorted(get_tunings()):
            self.all_tunings_combo.addItem(name, userData=name)
        self.all_tunings_combo.setEnabled(False)

        self._resolved_base_symbol = get_tunings()["Open G"].symbol

        open_g_index = self.all_tunings_combo.findText("Open G")
        self.all_tunings_combo.setCurrentIndex(open_g_index)

        self.specific_radio.toggled.connect(
            self.all_tunings_combo.setEnabled
        )

        self.all_tunings_combo.currentIndexChanged.connect(
            self._sync_from_named_tuning
        )

        # BO-154 -- capo support. Only meaningful alongside a
        # specific tuning (matches the CLI's own requirement:
        # --capo without --tuning is rejected by run_optimizer()
        # with "--capo requires --tuning to also be given.").
        # 0 means "no capo" and is passed to run_optimizer() as
        # None, matching --capo's own CLI default; 1-5 is the
        # only other valid range (run_optimizer() itself rejects
        # anything else).
        capo_label = QLabel("Capo:")
        capo_tooltip = (
            "A banjo capo clamps across the neck, raising the "
            "pitch of strings 1-4 only -- never the 5th (short) "
            "string, which stays open regardless. Each capo "
            "position raises those 4 strings by one semitone, so "
            "e.g. Open G (gDGBD) with capo 2 sounds as gEAC#E: "
            "the 5th string is still G, but strings 1-4 are each "
            "two semitones higher than the open tuning shown "
            "above. 0 means no capo. To also change the 5th "
            "string itself (a separate, real-world retuning-peg "
            "adjustment players sometimes make alongside a capo, "
            "not something the capo does on its own), use the "
            "5th string control below."
        )
        capo_label.setToolTip(capo_tooltip)

        self.capo_spin = QSpinBox()
        self.capo_spin.setMinimum(0)
        self.capo_spin.setMaximum(5)
        self.capo_spin.setValue(0)
        self.capo_spin.setEnabled(False)
        self.capo_spin.setToolTip(capo_tooltip)

        self.specific_radio.toggled.connect(
            self.capo_spin.setEnabled
        )

        self.capo_spin.valueChanged.connect(
            self._update_sounded_tuning_display
        )

        # BO-163 -- an independent 5th-string override. NOT
        # derived from capo by any formula -- confirmed directly,
        # during this feature's own investigation, against three
        # real reference tunings a capo-based formula could never
        # reproduce (see run_optimizer()'s own fifth_string
        # docstring entry for the full reasoning and all three).
        # "Unchanged" is a real, explicit, selectable option
        # (index 0, mapped to None below) rather than an empty/
        # blank state, since it's genuinely the common case, not
        # an edge case to leave implicit. The other 12 options are
        # main.PITCH_CLASS_TO_NOTE_NAME itself (reused directly,
        # not a separately hardcoded list), so this control can
        # never drift out of sync with what run_optimizer()'s own
        # sharp-only symbol convention actually produces.
        fifth_string_label = QLabel("5th string:")
        fifth_string_tooltip = (
            "Overrides the 5th string's own sounded pitch, "
            "independent of capo -- capo (above) never touches "
            "the 5th string on its own; this is for when you "
            "additionally retune it yourself (via its own tuning "
            "peg), a real, separate adjustment some players make "
            "on top of a capo. 'Unchanged' (the default) leaves "
            "the 5th string at the open tuning's own pitch, "
            "exactly as capo alone would."
        )
        fifth_string_label.setToolTip(fifth_string_tooltip)

        self.fifth_string_combo = QComboBox()
        self.fifth_string_combo.addItem("Unchanged", userData=None)
        for note_name in main.PITCH_CLASS_TO_NOTE_NAME:
            self.fifth_string_combo.addItem(
                note_name, userData=note_name
            )
        self.fifth_string_combo.setEnabled(False)
        self.fifth_string_combo.setToolTip(fifth_string_tooltip)

        self.specific_radio.toggled.connect(
            self.fifth_string_combo.setEnabled
        )

        self.fifth_string_combo.currentIndexChanged.connect(
            self._update_sounded_tuning_display
        )

        # BO-165 -- display-only: always the live result of Capo
        # tuning + Capo + 5th string (never the all-tunings picker
        # directly), computed via main.compute_sounded_tuning() --
        # the same function Optimize itself will call, so this is
        # never a second, potentially-drifting representation of
        # the tuning. Read-only (QLineEdit.setReadOnly, not a
        # label) so its text is still selectable/copyable.
        sounded_tuning_label = QLabel("Sounded tuning:")
        self.sounded_tuning_display = QLineEdit()
        self.sounded_tuning_display.setReadOnly(True)

        tuning_layout.addWidget(self.recommend_radio, 0, 0, 1, 2)
        tuning_layout.addWidget(
            QLabel("Number of tunings:"), 1, 1
        )
        tuning_layout.addWidget(self.num_tunings_spin, 1, 2)

        tuning_layout.addWidget(self.specific_radio, 2, 0, 1, 2)
        tuning_layout.addWidget(all_tuning_label, 3, 1)
        tuning_layout.addWidget(self.all_tunings_combo, 3, 2)
        tuning_layout.addWidget(capo_label, 4, 1)
        tuning_layout.addWidget(self.capo_spin, 4, 2)
        tuning_layout.addWidget(fifth_string_label, 5, 1)
        tuning_layout.addWidget(self.fifth_string_combo, 5, 2)
        tuning_layout.addWidget(sounded_tuning_label, 6, 1)
        tuning_layout.addWidget(self.sounded_tuning_display, 6, 2)

        # Initial state: populate the display with whatever the
        # default Capo tuning/capo/5th-string selections resolve
        # to, so it's never blank before the user touches anything.
        self._update_sounded_tuning_display()

        layout.addWidget(tuning_group)

        # --- Optimize ----------------------------------------------
        self.optimize_button = QPushButton("Optimize")
        self.optimize_button.clicked.connect(
            self._on_optimize_clicked
        )
        # BO-161 -- green and bold so it doesn't get lost in the
        # middle of the dialog; explicit :disabled state too,
        # since this button is already disabled during a run
        # (see _on_optimize_clicked below) and should visibly
        # look non-clickable then, not just silently ignore
        # clicks.
        self.optimize_button.setStyleSheet(
            "QPushButton {"
            "    background-color: #4CAF50;"
            "    color: white;"
            "    font-weight: bold;"
            "    padding: 8px 24px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #45a049;"
            "}"
            "QPushButton:disabled {"
            "    background-color: #a5d6a7;"
            "    color: #f0f0f0;"
            "}"
        )

        layout.addWidget(
            self.optimize_button, alignment=Qt.AlignHCenter
        )

        # --- Status --------------------------------------------
        self.status_label = QLabel("Status: Ready")
        layout.addWidget(self.status_label)

        # --- Results ---------------------------------------------
        self.results_view = QTextEdit()
        self.results_view.setReadOnly(True)
        self.results_view.setPlaceholderText(
            "Results will appear here after you click Optimize."
        )
        layout.addWidget(self.results_view)

        # --- Bottom buttons --------------------------------------
        bottom_layout = QHBoxLayout()

        self.open_output_button = QPushButton("Open Output")
        self.open_output_button.setEnabled(False)
        self.open_output_button.clicked.connect(
            self._on_open_output_clicked
        )

        settings_button = QPushButton("Settings...")
        settings_button.clicked.connect(self._on_settings_clicked)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        bottom_layout.addWidget(self.open_output_button)
        bottom_layout.addWidget(settings_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(close_button)

        layout.addLayout(bottom_layout)

        self._last_run_folder = None

    def _sync_from_named_tuning(self):
        """
        BO-165 -- decomposes the selected "Tuning:" entry (all 13)
        into Capo tuning / Capo / 5th string, reusing that Tuning's
        own real base_tuning/capo/fifth_string_note fields (never a
        second, separately-maintained mapping). For a tuning with
        no base_tuning (an ordinary, non-capo-derived tuning --
        base_tuning is None), it decomposes to itself with capo 0
        and 5th string Unchanged, since such a tuning already IS
        its own open base.
        """

        name = self.all_tunings_combo.currentData()

        if name is None:
            return

        tuning = get_tunings()[name]

        # BO-166 -- base_tuning is now always a plain, directly-
        # usable open-tuning symbol (e.g. "gCGCD"), never the old
        # "{name} ({symbol})" display string -- so no parsing or
        # second catalog lookup is needed here anymore, unlike the
        # BO-165 version of this method.
        if tuning.base_tuning is not None:
            base_symbol = tuning.base_tuning
            capo_value = tuning.capo
            fifth_string_value = tuning.fifth_string_note
        else:
            base_symbol = tuning.symbol
            capo_value = 0
            fifth_string_value = None

        # BO-166 -- resolved base is stored as internal state, not
        # a second visible dropdown (the former "Capo tuning" combo
        # was removed -- confirmed, during this feature's own
        # investigation, to be a strict subset of this "Tuning:"
        # combo's own list, adding no real capability of its own).
        self._resolved_base_symbol = base_symbol

        self.capo_spin.setValue(capo_value)

        fifth_string_index = self.fifth_string_combo.findData(
            fifth_string_value
        )

        if fifth_string_index != -1:
            self.fifth_string_combo.setCurrentIndex(
                fifth_string_index
            )

        # setCurrentIndex()/setValue() above each fire their own
        # signals on their own, which already call
        # _update_sounded_tuning_display -- but only when the
        # index/value genuinely changes. An explicit call here too
        # covers the case where the named tuning's own decomposition
        # happens to match whatever was already selected (so none
        # of those signals fire), ensuring the display is never
        # stale. Also the only place that picks up a changed
        # self._resolved_base_symbol on its own, since that's
        # internal state with no signal of its own to fire.
        self._update_sounded_tuning_display()

    def _update_sounded_tuning_display(self):
        """
        BO-165 -- live preview, computed via
        main.compute_sounded_tuning() (the same function Optimize
        itself calls through run_optimizer()) -- never a second,
        potentially-drifting computation of its own. Deliberately
        does not call run_optimizer() itself: that requires a real
        score file and runs the full analysis pipeline, wildly
        inappropriate for a field that must update on every capo/
        5th-string change with no score involved at all.

        BO-166 -- reads self._resolved_base_symbol (internal state,
        set by _sync_from_named_tuning() above) instead of a
        separate "Capo tuning" combo, which no longer exists.
        """

        fifth_string = self.fifth_string_combo.currentData()

        # 0 (the spinbox's own "no capo" value) must be passed as
        # None -- compute_sounded_tuning() itself only accepts None
        # or 1-5, matching --capo's own CLI convention throughout
        # this application; 0 itself is rejected. Same conversion
        # _on_optimize_clicked already applies for the real
        # Optimize call, just missed here initially and caught by
        # this method's own construction-time self-test.
        capo_value = (
            self.capo_spin.value()
            if self.capo_spin.value() > 0
            else None
        )

        try:
            _, sounded_symbol, _ = main.compute_sounded_tuning(
                self._resolved_base_symbol,
                capo_value,
                fifth_string
            )
        except ValueError:
            self.sounded_tuning_display.setText("")
            return

        self.sounded_tuning_display.setText(sounded_symbol)

    def _on_browse_clicked(self):

        scores_folder = _default_scores_folder()
        scores_folder.mkdir(parents=True, exist_ok=True)

        # BO-155 -- a real file picker. Defaults to opening in
        # scores/ (convenient if that's where most files already
        # are), but any .mscz file anywhere is now accepted --
        # see run_optimizer()'s own score_path parameter (BO-155),
        # which this now uses instead of score_filename whenever
        # the picked file isn't already inside scores/. BO-160 --
        # this default location itself is now settings-aware (see
        # _default_scores_folder() above), not the hardcoded
        # scores/ this always opened in before.
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a MuseScore file",
            str(scores_folder),
            "MuseScore files (*.mscz)"
        )

        if not file_path:
            return

        self.selected_score_path = Path(file_path)
        self.score_line_edit.setText(str(self.selected_score_path))

    def _on_optimize_clicked(self):

        if self.selected_score_path is None:
            QMessageBox.warning(
                self, "No score selected",
                "Please choose a score first."
            )
            return

        tuning_symbol = None
        capo = None
        fifth_string = None

        if self.specific_radio.isChecked():
            # BO-166 -- was self.capo_tuning_combo.currentData();
            # that combo is gone (see this class's own construction
            # above), replaced by internal state kept in sync by
            # _sync_from_named_tuning() whenever "Tuning:" changes.
            tuning_symbol = self._resolved_base_symbol

            if self.capo_spin.value() > 0:
                capo = self.capo_spin.value()

            fifth_string = self.fifth_string_combo.currentData()

        # BO-157 -- num_tunings is only meaningful under
        # "Recommended Tuning" -- default to 1 (matching
        # num_tunings_spin's own default) if "specific tuning" is
        # active, since the spinbox itself is disabled in that
        # state and its value shouldn't be trusted either way.
        # "Use specific tuning" always produces exactly one result
        # regardless of this value, so 1 vs. its actual disabled
        # value makes no practical difference here -- this is
        # about not reading a value from a control the user can't
        # currently see as meaningful, not about changing behavior.
        num_tunings = (
            self.num_tunings_spin.value()
            if self.recommend_radio.isChecked()
            else 1
        )

        self.status_label.setText("Status: Optimizing...")
        self.results_view.clear()
        self.optimize_button.setEnabled(False)
        self.open_output_button.setEnabled(False)
        QApplication.processEvents()

        try:
            result = main.run_optimizer(
                score_path=self.selected_score_path,
                tuning_symbol=tuning_symbol,
                capo=capo,
                num_tunings=num_tunings,
                fifth_string=fifth_string,
            )
        except ValueError as error:
            self.status_label.setText("Status: Error")
            QMessageBox.critical(self, "Could not optimize", str(error))
            self.optimize_button.setEnabled(True)
            return
        except Exception as error:
            self.status_label.setText("Status: Error")
            QMessageBox.critical(
                self, "Unexpected error",
                f"Something went wrong:\n{error}"
            )
            self.optimize_button.setEnabled(True)
            return

        self.optimize_button.setEnabled(True)
        self._last_run_folder = result["run_folder"]
        self.open_output_button.setEnabled(True)
        self.status_label.setText("Status: Done")

        self._display_result(result)

    def _display_result(self, result):

        lines = []

        for score_result in result["scores"]:

            lines.append(f"Title: {score_result['title']}")
            lines.append(f"Key: {score_result['key']}")
            lines.append("")

            requested = score_result["requested_tuning"]

            if requested is not None:
                lines.append(
                    f"Using requested tuning: {requested.symbol}"
                )
            else:
                lines.append("Recommended tunings:")

            lines.append("")

            for i, rec in enumerate(
                score_result["recommendations"], start=1
            ):
                lines.append(f"{i}. {rec.name} ({rec.symbol})")
                for advantage in rec.advantages:
                    lines.append(f"   - {advantage}")

            # BO-157 -- this GUI no longer requests alternatives
            # (see this class's own _on_optimize_clicked), so
            # additional_alternatives is always empty here now.
            # Not displayed -- removed rather than left as an
            # always-false dead branch.

            lines.append("")
            lines.append("Generated files:")

            for gen in score_result["generated_files"]:
                if gen["error"] is None:
                    lines.append(
                        f"   - {gen['tab_path'].name}"
                    )
                else:
                    lines.append(
                        f"   - Could not generate "
                        f"{gen['tuning_name']}: {gen['error']}"
                    )

        self.results_view.setPlainText("\n".join(lines))

    def _on_open_output_clicked(self):

        if self._last_run_folder is None:
            return

        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._last_run_folder))
        )

    def _on_settings_clicked(self):

        dialog = SettingsDialog(self)
        dialog.exec()


class SettingsDialog(QDialog):
    """
    BO-160 -- lets the user save a default scores/output folder,
    persisted via main.save_settings() (a small JSON file next to
    the .exe/main.py -- see that function's own docstring). Both
    fields are independent and optional: leaving one blank and
    saving means "use this application's original default" for
    that one, not "set it to blank" -- save_settings() only ever
    receives keys for fields that were genuinely filled in.

    Deliberately does not touch run_optimizer() or any in-flight
    optimization -- this dialog only ever reads/writes the
    settings file itself. The next Browse click or Optimize run
    picks up whatever was saved here on its own (see
    _default_scores_folder() and run_optimizer()'s own internal
    load_settings() call), not this dialog directly.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        current = main.load_settings(PROJECT_FOLDER)

        default_scores = PROJECT_FOLDER / "scores"
        default_output = PROJECT_FOLDER / "output"

        scores_group = QGroupBox("Default Scores Folder")
        scores_layout = QHBoxLayout(scores_group)

        self.scores_line_edit = QLineEdit(
            current.get("scores_folder", "")
        )
        self.scores_line_edit.setPlaceholderText(
            f"(default: {default_scores})"
        )

        scores_browse_button = QPushButton("Browse...")
        scores_browse_button.clicked.connect(
            lambda: self._browse_folder(self.scores_line_edit)
        )

        scores_layout.addWidget(self.scores_line_edit)
        scores_layout.addWidget(scores_browse_button)

        layout.addWidget(scores_group)

        output_group = QGroupBox("Default Output Folder")
        output_layout = QHBoxLayout(output_group)

        self.output_line_edit = QLineEdit(
            current.get("output_folder", "")
        )
        self.output_line_edit.setPlaceholderText(
            f"(default: {default_output})"
        )

        output_browse_button = QPushButton("Browse...")
        output_browse_button.clicked.connect(
            lambda: self._browse_folder(self.output_line_edit)
        )

        output_layout.addWidget(self.output_line_edit)
        output_layout.addWidget(output_browse_button)

        layout.addWidget(output_group)

        button_layout = QHBoxLayout()

        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save_clicked)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _browse_folder(self, line_edit):

        folder = QFileDialog.getExistingDirectory(
            self, "Select folder", line_edit.text() or str(PROJECT_FOLDER)
        )

        if folder:
            line_edit.setText(folder)

    def _on_save_clicked(self):

        # BO-160 -- only include a key when its field is
        # genuinely non-blank (see this class's own docstring):
        # a blank field means "fall back to the original
        # default", not "save an empty string as the default".
        settings = {}

        scores_text = self.scores_line_edit.text().strip()
        if scores_text:
            settings["scores_folder"] = scores_text

        output_text = self.output_line_edit.text().strip()
        if output_text:
            settings["output_folder"] = output_text

        try:
            main.save_settings(settings, PROJECT_FOLDER)
        except OSError as error:
            QMessageBox.critical(
                self, "Could not save settings",
                f"Settings could not be saved:\n{error}"
            )
            return

        self.accept()


def main_gui():
    app = QApplication(sys.argv)
    window = BanjoOptimizerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main_gui()
