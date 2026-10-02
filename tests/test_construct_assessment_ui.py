import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QLabel

from bart_spine_ui.planning.assessment import ScrewAssessment
from bart_spine_ui.planning.service import LEVEL_ORDER, parse_levels_of_interest
from bart_spine_ui.segmentation.totalsegmentator_service import (
    FULL_SPINE_ROIS,
    TotalSegmentatorService,
    rois_for_case,
)
from bart_spine_ui.ui.hu_analysis_dialog import HUPlot, hu_statistics
from bart_spine_ui.ui.pages.planning_construct_page import ConstructReviewWidget
from bart_spine_ui.ui.spine_level_selector import SpineLevelSelector


def test_full_spine_selection_roundtrip():
    app = QApplication.instance() or QApplication([])
    selector = SpineLevelSelector(['L3', 'L5'])
    changed = []
    selector.selection_changed.connect(lambda: changed.append(True))
    selector.buttons['C1'].click()
    selector.buttons['S1'].click()
    selector.buttons['L3'].click()
    assert selector.selected_levels() == ['C1', 'L5', 'S1']
    assert parse_levels_of_interest(', '.join(selector.selected_levels())) == selector.selected_levels()
    assert len(parse_levels_of_interest('C1-S1')) == 25
    assert list(selector.buttons) == list(LEVEL_ORDER)
    assert len(changed) == 3
    assert set(rois_for_case('Spine', selector.selected_levels())) <= set(FULL_SPINE_ROIS)
    assert TotalSegmentatorService._validate_rois(('vertebrae_C1', 'vertebrae_S1')) == (
        'vertebrae_C1', 'vertebrae_S1')
    selector.close()
    app.processEvents()


@pytest.mark.parametrize("size", [(1280, 800), (1280, 720), (1024, 768)])
def test_construct_density_and_rod_controls(tmp_path, size):
    from PySide6.QtWidgets import QScrollArea

    app = QApplication.instance() or QApplication([])
    review = ConstructReviewWidget()
    from bart_spine_ui.ui.theme import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    review.resize(*size)
    review.attach_three_d(QLabel('3D construct'))
    levels = ['L1', 'L2', 'L3', 'L4', 'L5']
    accepted = {(level, side) for level in levels for side in ('left', 'right')}
    review.set_construct(levels, accepted, {})
    result = ScrewAssessment(.3, 'B', np.array([0., 10., 20.]),
                             np.array([100., 400., np.nan]), np.array([1., 1., 0.]),
                             breach_point_lps=(3.3, -15., 0.), bone_point_lps=(3., -15., 0.),
                             breach_depth_mm=15., voxel_spacing_mm=(.8, .8, 1.))
    panel = review.assessment_panel
    panel.set_results({key: result for key in accepted})
    review.show()
    app.processEvents()
    assert not review.findChildren(QScrollArea)
    assert not panel.findChildren(HUPlot)
    assert len(panel.grade_buttons) == 10
    assert review.rod_info.height() == 190
    assert review.three_d_card.height() < review.assessment_panel.height()
    assert review.size().width() == size[0]
    assert review.size().height() == size[1]
    for widget in (review.left_rod, review.right_rod, panel.hu_confirmed,
                   *panel.grade_buttons.values()):
        assert widget.isVisible()
        assert review.rect().contains(widget.mapTo(review, widget.rect().bottomRight()))
    assert review.grab().save(str(tmp_path/'construct.png'))
    panel.hu_confirmed.click()
    app.processEvents()
    assert panel.hu_dialog.isVisible()
    assert panel.hu_dialog.cards[('L1', 'left')].result is result
    assert panel.hu_dialog.grab().save(str(tmp_path/'hu-analysis.png'))
    panel.hu_dialog.close()
    assert not panel.hu_confirmed.isChecked()
    toggled = []
    review.rods_toggled.connect(toggled.append)
    review.rods_visible.click()
    assert toggled == [False]
    # Full-spine cases use the same fixed-size review with page controls.
    review.set_construct(list(LEVEL_ORDER), accepted, {})
    app.processEvents()
    assert review.size().width() == size[0]
    assert review.size().height() == size[1]
    assert panel.next.isVisible()
    review.close()
    app.processEvents()


def test_hu_popup_statistics_and_sample_inspection():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from bart_spine_ui.ui.screw_assessment_panel import ScrewAssessmentPanel

    app = QApplication.instance() or QApplication([])
    panel = ScrewAssessmentPanel()
    result = ScrewAssessment(0, 'A', np.array([0., 10., 20.]),
                             np.array([100., 400., np.nan]), np.array([1., .5, 0.]))
    panel.set_results({('L3', 'left'): result})
    panel.show()
    panel.hu_confirmed.click()
    app.processEvents()
    dialog = panel.hu_dialog
    stats = hu_statistics(result)
    assert stats['mean'] == stats['median'] == 250
    assert stats['quartiles'] == (175, 325)
    assert stats['sample_support'] == .5
    assert stats['coverage'] is None
    assert stats['count'] == 2
    dialog.cards[("L3", "left")].click()
    dialog = dialog.detail_dialog
    plot = dialog.profile
    box = plot.plot_rect()
    QTest.mouseClick(plot, Qt.MouseButton.LeftButton,
                     pos=QPoint(int(box.center().x()), int(box.center().y())))
    assert plot.selected_index == 1
    assert '400 HU' in dialog.readout.text()
    assert '50%' in dialog.readout.text()
    QTest.keyClick(plot, Qt.Key.Key_End)
    assert 'No sample' in dialog.readout.text()
    assert '20.0 mm' in dialog.readout.text()
    panel.clear()
    assert not dialog.isVisible()
    assert not panel.hu_confirmed.isEnabled()
    panel.close()


def test_grading_pages_without_bars_or_scroll_and_labels_skipped():
    from PySide6.QtWidgets import QScrollArea

    from bart_spine_ui.ui.screw_assessment_panel import ScrewAssessmentPanel

    app = QApplication.instance() or QApplication([])
    panel = ScrewAssessmentPanel()
    levels = ['T12', 'L1', 'L2', 'L3', 'L4', 'L5']
    panel.set_targets(levels, {('L1', 'left')}, {('L2', 'right')})
    panel.set_results({('L1', 'left'): ScrewAssessment(
        0, 'A', np.array([0., 10.]), np.array([100., 200.]), np.ones(2))})
    assert len(panel.grade_buttons) == 10
    assert panel.grade_buttons[('L2', 'right')].text() == 'Skipped'
    assert 'G–R A' in panel.grade_buttons[('L1', 'left')].text()
    assert not panel.findChildren(QScrollArea)
    panel.next.click()
    assert set(panel.grade_buttons) == {('L5', 'left'), ('L5', 'right')}
    assert not panel.next.isEnabled()
    panel.previous.click()
    assert ('T12', 'left') in panel.grade_buttons
    panel.close()
    app.processEvents()


def test_hu_statistics_missing_constant_and_unclipped_values():
    from bart_spine_ui.ui.hu_analysis_dialog import HUDetailDialog

    app = QApplication.instance() or QApplication([])
    results = {}
    for level, values in [('L1', [np.nan, np.nan]), ('L2', [500., 500.]),
                          ('L3', [-200., 1800.])]:
        results[(level, 'left')] = ScrewAssessment(
            0, 'A', np.array([0., 20.]), np.array(values), np.zeros(2))
    assert hu_statistics(results[('L1', 'left')])['mean'] is None
    assert hu_statistics(results[('L3', 'left')])['mean'] == 800
    dialog = HUDetailDialog(results)
    dialog.show()
    for i in range(3):
        dialog.selector.setCurrentIndex(i)
        app.processEvents()
        assert not dialog.grab().isNull()
    assert '-200 HU' in dialog.readout.text()
    dialog.close()


def test_worker_uses_fixed_entry_band(monkeypatch):
    from bart_spine_ui.ui.screw_assessment_panel import AssessmentWorker

    observed = []

    def assess(self, plan, volume, *, entry_exclusion_mm):
        observed.append(entry_exclusion_mm)
        return 'result'

    monkeypatch.setattr('bart_spine_ui.ui.screw_assessment_panel.ScrewAssessmentService.assess', assess)
    worker = AssessmentWorker(None, None, {('L3', 'left'): object()})
    results = []
    worker.completed.connect(results.append)
    worker.run()
    assert observed == [10]
    assert results == [{('L3', 'left'): 'result'}]


def test_breach_location_control_distinguishes_depth_from_breach():
    from PySide6.QtWidgets import QPushButton

    from bart_spine_ui.ui.screw_assessment_panel import ScrewAssessmentPanel

    app = QApplication.instance() or QApplication([])
    panel = ScrewAssessmentPanel()
    result = ScrewAssessment(.3, 'B', np.array([0., 20.]), np.array([100., 200.]),
                             np.ones(2), breach_point_lps=(12.3, 20., 30.),
                             bone_point_lps=(12., 20., 30.), breach_depth_mm=15.,
                             voxel_spacing_mm=(.8, .8, 1.))
    panel.set_results({('L3', 'left'): result})
    labels = [label.text() for label in panel.findChildren(QLabel)]
    assert any('0.3 mm' in text for text in labels)
    assert any('At 15.0 mm from entry' in text for text in labels)
    assert any('Below voxel spacing' in text for text in labels)
    located = []
    panel.locate_breach_requested.connect(located.append)
    button = next(button for button in panel.findChildren(QPushButton) if button.text() == 'Locate selected breach in 3D')
    button.click()
    assert located == [('L3', 'left')]
    assert button.minimumHeight() >= 38
    panel.close()
    app.processEvents()


def test_anatomical_hu_overview_shared_scale_status_paging_and_touch(tmp_path):
    from PySide6.QtWidgets import QScrollArea

    from bart_spine_ui.ui.hu_analysis_dialog import HUAnalysisDialog

    app = QApplication.instance() or QApplication([])
    results = {}
    for i, level in enumerate(('L1', 'L2', 'L3', 'L4', 'L5')):
        for side in ('left', 'right'):
            hu = 150 + 45*np.sin(np.linspace(0, 5, 41)) + i*12
            results[(level, side)] = ScrewAssessment(
                0., 'A', np.linspace(0, 40, 41), hu, np.full(41, .35), model_coverage=1.)
    results[('L3', 'right')].model_coverage = .82
    results[('L3', 'right')].grade = 'B'
    results[('L3', 'right')].breach_mm = 1.1
    dialog = HUAnalysisDialog(results, skipped={('L2', 'right')})
    dialog.resize(1024, 700)
    dialog.show()
    app.processEvents()
    assert dialog.size().width() == 1024
    assert dialog.size().height() == 700
    assert len(dialog.cards) == 6
    assert not dialog.findChildren(QScrollArea)
    for card in dialog.cards.values():
        assert card.minimumHeight() >= 154
        assert card.limits == dialog.limits
        assert dialog.rect().contains(card.mapTo(dialog, card.rect().bottomRight()))
    assert dialog.cards[('L1', 'left')].coverage_text == '100%'
    assert dialog.cards[('L1', 'left')].status_text == '✓ G–R A'
    assert not dialog.cards[('L2', 'right')].isEnabled()
    assert dialog.cards[('L3', 'right')].status_text == '⚠ REVIEW'
    assert dialog.cards[('L3', 'right')].coverage_text == '82%'
    assert dialog.grab().save(str(tmp_path/'overview.png'))
    dialog.cards[('L3', 'right')].click()
    assert dialog.detail_dialog.isVisible()
    assert dialog.detail_dialog.profile.result is results[('L3', 'right')]
    dialog.detail_dialog.close()
    dialog.next.click()
    assert {key[0] for key in dialog.cards} == {'L4', 'L5'}
    dialog.focus_target(('L2', 'left'))
    assert dialog.page == 0
    dialog.open_detail(('L1', 'left'))
    detail = dialog.detail_dialog
    dialog.reject()  # Escape/Reject must close the separate detail window too.
    assert not detail.isVisible()
    assert not dialog.isVisible()


def test_low_hu_does_not_trigger_density_cutoff_or_invent_coverage():
    from bart_spine_ui.ui.hu_analysis_dialog import HUScrewCard, review_reasons

    app = QApplication.instance() or QApplication([])
    result = ScrewAssessment(0., 'A', np.array([0., 20.]), np.array([20., 30.]),
                             np.array([.3, .9]), model_coverage=1.)
    assert not review_reasons(result)
    result.model_coverage = None
    card = HUScrewCard(('L1', 'left'), result, (0., 100.))
    assert card.coverage_text == '—'
    assert card.status_text == '⚠ REVIEW'
    result.hu[:] = np.nan
    assert 'Missing CT samples' in review_reasons(result)
    card.close()
    app.processEvents()
