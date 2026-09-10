"""
BO-166 -- removes the separate "Capo tuning" dropdown BO-165
introduced (confirmed, during BO-166's own investigation, to be a
strict subset of the "Tuning:" combo's own list -- every value it
could ever show was already directly selectable there, so it added
no real capability). The resolved base tuning is now internal
state (BanjoOptimizerWindow._resolved_base_symbol) rather than a
second visible selector. Also removes Triple D Darling Cora from
the named-tuning catalog, and generalizes the automatic capo/5th-
string decomposition (previously Double D only) to three more
named tunings: A Minor, A Modal Sawmill, and Open A.

Supersedes tests/test_bo165_capo_tuning_gui.py, which asserted
against the now-removed capo_tuning_combo widget directly.

Uses the same Qt offscreen-platform, direct-widget-construction
pattern as every other GUI test file in this project (no real
display needed).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from PySide6.QtWidgets import QApplication

import gui
from tunings import get_tunings

# A single shared QApplication -- required once per process for
# any QWidget construction, same convention as this project's
# other GUI tests.
_app = QApplication.instance() or QApplication(sys.argv)


def test_triple_d_darling_cora_removed_from_catalog():

    assert "Triple D Darling Cora" not in get_tunings()


def test_triple_d_darling_cora_removed_from_all_tunings_combo():

    window = gui.BanjoOptimizerWindow()

    assert (
        window.all_tunings_combo.findText("Triple D Darling Cora")
        == -1
    )


def test_capo_tuning_widget_no_longer_exists():
    """
    The separate "Capo tuning" dropdown (BO-165) is gone entirely --
    confirmed by the attribute itself being absent, not just unused.
    """

    window = gui.BanjoOptimizerWindow()

    assert not hasattr(window, "capo_tuning_combo")


def test_all_tunings_combo_contains_all_12_remaining_named_tunings():

    window = gui.BanjoOptimizerWindow()

    assert window.all_tunings_combo.count() == 12

    combo_names = {
        window.all_tunings_combo.itemText(i)
        for i in range(window.all_tunings_combo.count())
    }

    assert combo_names == set(get_tunings().keys())


def test_double_d_present_in_all_tunings_combo():

    window = gui.BanjoOptimizerWindow()

    assert window.all_tunings_combo.findText("Double D") != -1


def test_capo_number_range_is_0_to_5():

    window = gui.BanjoOptimizerWindow()

    assert window.capo_spin.minimum() == 0
    assert window.capo_spin.maximum() == 5


def test_a_minor_auto_resolves():

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("A Minor")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert window._resolved_base_symbol == "gDGBbD"
    assert window.capo_spin.value() == 2
    assert window.fifth_string_combo.currentText() == "A"
    assert window.sounded_tuning_display.text() == "aEACE"


def test_a_modal_sawmill_auto_resolves():

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("A Modal Sawmill")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert window._resolved_base_symbol == "gDGCD"
    assert window.capo_spin.value() == 2
    assert window.fifth_string_combo.currentText() == "A"
    assert window.sounded_tuning_display.text() == "aEADE"


def test_open_a_auto_resolves():

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("Open A")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert window._resolved_base_symbol == "gDGBD"
    assert window.capo_spin.value() == 2
    assert window.fifth_string_combo.currentText() == "A"
    assert window.sounded_tuning_display.text() == "aEAC#E"


def test_double_d_still_auto_resolves():
    """
    Double D is the working model this whole feature generalizes --
    must continue producing exactly the same result as before.
    """

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("Double D")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert window._resolved_base_symbol == "gCGCD"
    assert window.capo_spin.value() == 2
    assert window.fifth_string_combo.currentText() == "A"
    assert window.sounded_tuning_display.text() == "aDADE"


def test_manually_changing_capo_after_auto_population_updates_display():

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("Open A")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert window.sounded_tuning_display.text() == "aEAC#E"

    window.capo_spin.setValue(3)

    # base gDGBD + capo 3 (5th string still manually held at A,
    # unaffected by the capo change) -> strings 1-4 each up 3
    # semitones from Open A's own capo-2 starting point
    assert window.sounded_tuning_display.text() == "aFA#DF"


def test_manually_changing_fifth_string_after_auto_population_updates_display():

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("Open A")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert window.sounded_tuning_display.text() == "aEAC#E"

    fifth_idx = window.fifth_string_combo.findText("F")
    window.fifth_string_combo.setCurrentIndex(fifth_idx)

    assert window.sounded_tuning_display.text() == "fEAC#E"


def test_selecting_ordinary_tuning_resolves_to_itself():
    """
    A tuning with no base_tuning (Open G: not capo-derived) should
    resolve to itself, capo 0, 5th string Unchanged -- it already
    IS its own open base.
    """

    window = gui.BanjoOptimizerWindow()

    idx = window.all_tunings_combo.findText("Open G")
    window.all_tunings_combo.setCurrentIndex(idx)

    assert window._resolved_base_symbol == "gDGBD"
    assert window.capo_spin.value() == 0
    assert window.fifth_string_combo.currentText() == "Unchanged"
    assert window.sounded_tuning_display.text() == "gDGBD"


def test_default_state_is_open_g():
    """
    The default User-specific configuration on window construction,
    before the user touches anything.
    """

    window = gui.BanjoOptimizerWindow()

    assert window.all_tunings_combo.currentText() == "Open G"
    assert window._resolved_base_symbol == "gDGBD"
    assert window.capo_spin.value() == 0
    assert window.fifth_string_combo.currentText() == "Unchanged"
    assert window.sounded_tuning_display.text() == "gDGBD"


def test_resulting_tuning_passed_correctly_to_optimizer():
    """
    End-to-end: selecting a named capo tuning and clicking Optimize
    must genuinely pass the resolved base/capo/5th-string through
    to run_optimizer(), not just update the display.
    """

    window = gui.BanjoOptimizerWindow()

    window.selected_score_path = (
        gui._default_scores_folder() / "White Christmas.mscz"
    )
    window.score_line_edit.setText(str(window.selected_score_path))
    window.specific_radio.setChecked(True)

    idx = window.all_tunings_combo.findText("A Minor")
    window.all_tunings_combo.setCurrentIndex(idx)

    window._on_optimize_clicked()

    assert "Status: Done" in window.status_label.text()
    assert "aEACE" in window.results_view.toPlainText()


def test_new_tuning_controls_disabled_under_recommended_tuning():

    window = gui.BanjoOptimizerWindow()

    # recommend_radio is checked by default
    assert window.all_tunings_combo.isEnabled() is False

    window.specific_radio.setChecked(True)

    assert window.all_tunings_combo.isEnabled() is True

    window.recommend_radio.setChecked(True)

    assert window.all_tunings_combo.isEnabled() is False


def test_recommended_tuning_num_tunings_control_unaffected():
    """
    Confirms BO-166 left the Recommended Tuning section's own
    control (num_tunings_spin, from BO-157) completely untouched --
    still enabled by default, still disabled under specific tuning.
    """

    window = gui.BanjoOptimizerWindow()

    assert window.num_tunings_spin.isEnabled() is True

    window.specific_radio.setChecked(True)

    assert window.num_tunings_spin.isEnabled() is False
